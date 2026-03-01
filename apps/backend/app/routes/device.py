from flask import Blueprint, request
from app.utils.response import success, fail
import json
import os
import paramiko
import urllib.request
import urllib.parse
import threading
from app.extensions import db
from app.models.device import Device
from app.models.model import ModelVersion

device_bp = Blueprint("device", __name__, url_prefix="/api")

PROM_DIR = "/data/workspace/hdap-platform/infra/prometheus"
TARGETS_FILE = os.path.join(PROM_DIR, "targets.json")
REGISTRY_FILE = os.path.join(PROM_DIR, "devices.json")
JETSON_LOCAL_DIR = "/data/workspace/hdap-platform/infra/jetson"


def _read_targets():
    if not os.path.exists(TARGETS_FILE):
        return []
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def _write_targets(items):
    os.makedirs(PROM_DIR, exist_ok=True)
    with open(TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _append_prom_targets(ip: str, labels: dict):
    items = _read_targets()
    # 两个端点：9100 与 9200
    targets = [f"{ip}:9100", f"{ip}:9200"]
    for t in targets:
        if not any(entry.get("targets") == [t] for entry in items):
            items.append({"targets": [t], "labels": labels})
    _write_targets(items)


def _remove_prom_targets(ip: str):
    items = _read_targets()
    filtered = [entry for entry in items if ip not in (entry.get("targets", [""])[0])]
    _write_targets(filtered)


def _read_registry():
    if not os.path.exists(REGISTRY_FILE):
        return []
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _write_registry(items):
    os.makedirs(PROM_DIR, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _registry_upsert(ip: str, device_type: str):
    # mirror into DB
    dev = Device.query.filter_by(ip=ip).first()
    if not dev:
        dev = Device(ip=ip, type=device_type)
        db.session.add(dev)
    else:
        dev.type = device_type
    db.session.commit()
    # keep json registry for compatibility
    items = _read_registry()
    for it in items:
        if it.get("ip") == ip:
            it["type"] = device_type
            _write_registry(items)
            return
    items.append({"ip": ip, "type": device_type, "status": "offline"})
    _write_registry(items)


def _registry_set_status(ip: str, status: str):
    dev = Device.query.filter_by(ip=ip).first()
    if dev:
        dev.status = status
        db.session.commit()
    items = _read_registry()
    for it in items:
        if it.get("ip") == ip:
            it["status"] = status
    _write_registry(items)


def _ssh_bootstrap_jetson(ip: str, username: str, password: str, port: int = 22):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password, port=port, timeout=10)

    sftp = ssh.open_sftp()
    remote_dir = "/opt/hdap-jetson"
    try:
        sftp.mkdir(remote_dir)
    except Exception:
        pass

    files = [
        (os.path.join(JETSON_LOCAL_DIR, "install_node_exporter.sh"), f"{remote_dir}/install_node_exporter.sh"),
        (os.path.join(JETSON_LOCAL_DIR, "install_jtop_exporter.sh"), f"{remote_dir}/install_jtop_exporter.sh"),
        (os.path.join(JETSON_LOCAL_DIR, "jtop_exporter.py"), f"{remote_dir}/jtop_exporter.py"),
    ]
    for src, dst in files:
        sftp.put(src, dst)
    sftp.close()

    sudo = "" if username == "root" else "sudo -n "
    cmds = [
        f"{sudo}chmod +x {remote_dir}/install_node_exporter.sh {remote_dir}/install_jtop_exporter.sh",
        f"{sudo}bash {remote_dir}/install_node_exporter.sh",
        f"{sudo}bash {remote_dir}/install_jtop_exporter.sh {remote_dir}/jtop_exporter.py",
    ]
    for cmd in cmds:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        _ = stdout.read()
        err = stderr.read()
        if err:
            # 不中断，继续后续步骤；记录错误用于返回
            pass

    ssh.close()


@device_bp.post("/devices/bootstrap")
def devices_bootstrap():
    body = request.json or {}
    ip = body.get("ip")
    username = body.get("username")
    password = body.get("password")
    device_type = body.get("deviceType", "Jetson Xavier NX")
    port = int(body.get("port", 22))
    if not ip or not username or not password:
        return fail(message="缺少必填参数 ip/username/password", code=400, http_status=400)
    try:
        labels = {"device_id": f"{ip}", "device_type": device_type, "job": "jetson"}
        _append_prom_targets(ip, labels)
        _registry_upsert(ip, device_type)
        _registry_set_status(ip, "online")

        def worker():
            try:
                _ssh_bootstrap_jetson(ip, username, password, port)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
        return success(message="设备引导安装已启动", data={"ip": ip})
    except Exception as e:
        return fail(message=f"引导安装失败: {e}", code=500, http_status=500)


@device_bp.get("/devices/status")
def device_status():
    ip = request.args.get("ip")
    if not ip:
        return fail(message="缺少 ip", code=400, http_status=400)
    try:
        targets = _read_targets()
        in_targets = any(ip in (entry.get("targets", [""])[0]) for entry in targets)
        def http_get(url: str, timeout: int = 5):
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except Exception:
                return None
        node_alive = http_get(f"http://{ip}:9100/-/healthy", 2) is not None or http_get(f"http://{ip}:9100/metrics", 2) is not None
        tegr_alive = http_get(f"http://{ip}:9200/metrics", 2) is not None
        prom_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
        prom_ok = http_get(f"{prom_url}/-/healthy", 3) is not None
        def prom_query(query: str):
            try:
                url = f"{prom_url}/api/v1/query?query=" + urllib.parse.quote(query)
                data = http_get(url, 5)
                if not data:
                    return None
                return json.loads(data)
            except Exception:
                return None
        def is_up(res):
            try:
                v = res["data"]["result"][0]["value"][1]
                return float(v) == 1.0
            except Exception:
                return False
        up_node = is_up(prom_query(f"up{{instance='{ip}:9100'}}")) if prom_ok else False
        up_jetson = is_up(prom_query(f"up{{instance='{ip}:9200'}}")) if prom_ok else False
        return success(data={
            "inTargets": in_targets,
            "nodeExporterAlive": node_alive,
            "tegrastatsAlive": tegr_alive,
            "promReachable": prom_ok,
            "nodeExporterUp": up_node,
            "tegrastatsUp": up_jetson,
        })
    except Exception as e:
        return fail(message=f"状态查询失败: {e}", code=500, http_status=500)


@device_bp.post("/devices/abort")
def device_abort():
    body = request.json or {}
    ip = body.get("ip")
    username = body.get("username")
    password = body.get("password")
    port = int(body.get("port", 22))
    if not ip:
        return fail(message="缺少 ip", code=400, http_status=400)
    # 停止设备端服务
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, port=port, timeout=10)
        for cmd in [
            "sudo systemctl stop node_exporter || true",
            "sudo systemctl stop tegrastats-exporter || true",
            "sudo systemctl stop jtop-exporter || true",
        ]:
            ssh.exec_command(cmd)
        ssh.close()
    except Exception:
        # 忽略设备侧错误，继续撤销targets
        pass
    # 撤销targets
    _remove_prom_targets(ip)
    _registry_set_status(ip, "offline")
    return success(message="已终止并清理设备采集")


@device_bp.post("/devices/remove")
def device_remove():
    body = request.json or {}
    ip = body.get("ip")
    if not ip:
        return fail(message="缺少 ip", code=400, http_status=400)
    _remove_prom_targets(ip)
    # 从注册表移除
    items = _read_registry()
    items = [it for it in items if it.get("ip") != ip]
    _write_registry(items)
    # 标记凭证不可用，但保留设备记录
    dev = Device.query.filter_by(ip=ip).first()
    if dev:
        dev.username = None
        dev.password = None
        dev.status = "offline"
        dev.removed = True
        db.session.commit()
    return success(message="已从采集中移除设备，凭证已标记为不可用")


@device_bp.post("/devices/register")
def device_register():
    body = request.json or {}
    ip = body.get("ip")
    username = body.get("username")
    password = body.get("password")
    device_type = body.get("deviceType", "Unknown")
    port = int(body.get("port", 22))
    if not ip:
        return fail(message="缺少 ip", code=400, http_status=400)
    dev = Device.query.filter_by(ip=ip).first()
    if not dev:
        dev = Device(ip=ip)
        db.session.add(dev)
    # 若之前被移除，则恢复为未移除状态
    dev.username = username
    dev.password = password
    dev.port = port
    dev.type = device_type
    dev.status = "offline"
    dev.removed = False
    db.session.commit()
    _registry_upsert(ip, device_type)
    _registry_set_status(ip, "offline")
    return success(message="设备已登记为离线，可随时上线", data={"ip": ip})




@device_bp.post("/devices/online")
def device_online():
    body = request.json or {}
    ip = body.get("ip")
    username = body.get("username")
    password = body.get("password")
    device_type = body.get("deviceType", "Jetson Xavier NX")
    port = int(body.get("port", 22))
    if not ip:
        return fail(message="缺少 ip", code=400, http_status=400)
    try:
        labels = {"device_id": f"{ip}", "device_type": device_type, "job": "jetson"}
        # 若提供凭据，执行安装；否则仅在采集端已运行时加入targets
        if username and password:
            # 保存凭据以便后续下线后自动上线
            dev = Device.query.filter_by(ip=ip).first()
            if not dev:
                dev = Device(ip=ip)
                db.session.add(dev)
            dev.username = username
            dev.password = password
            dev.port = port
            dev.type = device_type
            dev.removed = False
            db.session.commit()
            _ssh_bootstrap_jetson(ip, username, password, port)
            _append_prom_targets(ip, labels)
            _registry_upsert(ip, device_type)
            _registry_set_status(ip, "online")
            return success(message="设备已上线并加入采集", data={"ip": ip})
        # 无凭据：尝试从数据库读取凭据并安装；否则检查设备端是否已有采集服务在跑
        dev = Device.query.filter_by(ip=ip).first()
        if dev and dev.username and dev.password:
            dev.removed = False
            db.session.commit()
            _ssh_bootstrap_jetson(ip, dev.username, dev.password, dev.port or 22)
            _append_prom_targets(ip, labels)
            _registry_upsert(ip, device_type or (dev.type or "Unknown"))
            _registry_set_status(ip, "online")
            return success(message="已使用保存的凭据上线并加入采集", data={"ip": ip})
        def http_get(url: str, timeout: int = 3):
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except Exception:
                return None
        node_alive = http_get(f"http://{ip}:9100/metrics") is not None
        jet_alive = http_get(f"http://{ip}:9200/metrics") is not None
        if node_alive and jet_alive:
            _append_prom_targets(ip, labels)
            _registry_upsert(ip, device_type)
            _registry_set_status(ip, "online")
            return success(message="已检测到采集端运行，设备已上线并加入采集", data={"ip": ip})
        return fail(message="设备端未运行采集服务，需提供用户名与密码以安装后上线", code=400, http_status=400)
    except Exception as e:
        return fail(message=f"上线失败: {e}", code=500, http_status=500)


@device_bp.post("/devices/offline")
def device_offline():
    body = request.json or {}
    ip = body.get("ip")
    username = body.get("username")
    password = body.get("password")
    port = int(body.get("port", 22))
    if not ip:
        return fail(message="缺少 ip", code=400, http_status=400)
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, port=port, timeout=10)
        for cmd in [
            "sudo systemctl stop node_exporter || true",
            "sudo systemctl stop tegrastats-exporter || true",
            "sudo systemctl stop jtop-exporter || true",
        ]:
            ssh.exec_command(cmd)
        ssh.close()
    except Exception:
        pass
    _remove_prom_targets(ip)
    _registry_set_status(ip, "offline")
    return success(message="设备已下线（停止服务并从采集中移除，但保留登记）")


@device_bp.get("/devices/types")
def device_types():
    try:
        q = db.session.query(Device.type).distinct().all()
        names = {row[0] for row in q if row and row[0]}
        
        # Also include types from performance data
        q2 = db.session.query(ModelVersion.device_type).distinct().all()
        for row in q2:
            if row and row[0]:
                names.add(row[0])

        registry = _read_registry()
        for it in registry:
            t = it.get("type")
            if t:
                names.add(t)
        items = sorted(names)
        return success(data={"items": items})
    except Exception as e:
        return fail(message=f"查询设备类型失败: {e}", code=500, http_status=500)
