from flask import Blueprint
from flask import request
from app.utils.response import success, fail
import os
import json
import urllib.request
import urllib.parse
from app.models.surrogate_task import SurrogateTask
from app.extensions import db

PROM_DIR = "/data/workspace/hdap-platform/infra/prometheus"
TARGETS_FILE = os.path.join(PROM_DIR, "targets.json")

metrics_bp = Blueprint("metrics", __name__, url_prefix="/api")


def receive_metrics_internal(payload):
    """
    Internal function to handle metrics report from services or external agents
    payload: {task_id, device_ip, metrics: [...]}
    """
    task_id = payload.get('task_id')
    if not task_id:
        return
        
    task = SurrogateTask.query.get(task_id)
    if not task:
        return
        
    data_dir = os.path.join(os.getcwd(), 'data', 'surrogate_tasks', str(task_id))
    os.makedirs(data_dir, exist_ok=True)
    data_file = os.path.join(data_dir, 'collected_data.json')
    
    # Read existing
    existing_data = []
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r') as f:
                existing_data = json.load(f)
        except:
            pass
            
    # Append new data (check duplicates if needed, but simple append for now)
    existing_data.append(payload)
    
    with open(data_file, 'w') as f:
        json.dump(existing_data, f)
        
    # Check progress
    # If we have received data from X devices?
    # For now, let's just update progress to some value or let it be 'running'
    # Update sample count in training_params for UI
    try:
        current_params = json.loads(task.training_params or '{}')
        
        # Calculate stats
        total_samples = 0
        device_coverage = len(set(d.get('device_ip') for d in existing_data))
        
        for d in existing_data:
            metrics = d.get('metrics', [])
            total_samples += len(metrics)
            
        if 'collection_metrics' not in current_params:
            current_params['collection_metrics'] = []
            
        # Append a snapshot
        import datetime
        snapshot = {
            'time': datetime.datetime.now().isoformat(),
            'samples': total_samples,
            'devices': device_coverage
        }
        current_params['collection_metrics'].append(snapshot)
        
        task.training_params = json.dumps(current_params, ensure_ascii=False)
    except Exception as e:
        print(f"Error updating collection metrics: {e}")

    # If we assume we wait for all devices in device_list
    if task.device_list:
        target_devs = set(task.device_list.split(','))
        reported_devs = set([d.get('device_ip') for d in existing_data])
        
        if target_devs.issubset(reported_devs) or len(reported_devs) >= len(target_devs):
            task.progress = 100
            task.status = 'succeeded'
            db.session.commit()
    else:
        # If no explicit list, maybe we just mark done after first report?
        # Or wait for user to stop?
        # Let's mark succeeded for demo flow
        task.progress = 100
        task.status = 'succeeded'
        db.session.commit()

@metrics_bp.post("/metrics/report")
def report_metrics():
    """
    Endpoint for agents to report collected metrics
    """
    data = request.json or {}
    receive_metrics_internal(data)
    return success(message="Metrics received")



def _read_targets():
    if not os.path.exists(TARGETS_FILE):
        return []
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def _http_get(url: str, timeout: int = 5):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def _prom_query(prom_url: str, query: str):
    try:
        url = f"{prom_url}/api/v1/query?query=" + urllib.parse.quote(query)
        data = _http_get(url, 8)
        if not data:
            return None
        return json.loads(data)
    except Exception:
        return None


def _get_value(res, instance):
    try:
        for item in res.get("data", {}).get("result", []):
            if item.get("metric", {}).get("instance") == instance:
                return float(item.get("value", [0, 0])[1])
    except Exception:
        return None
    return None


@metrics_bp.get("/devices/metrics")
def devices_metrics():
    prom_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

    # merge: registry + targets; registry作为源，targets决定是否采集中
    from app.routes.device import _read_registry
    registry = _read_registry()
    devices = {it.get("ip"): {"ip": it.get("ip"), "deviceType": it.get("type", "Unknown"), "regStatus": it.get("status", "offline")} for it in registry}
    targets = _read_targets()
    for entry in targets:
        tgts = entry.get("targets", [])
        if not tgts:
            continue
        inst = tgts[0]
        ip = inst.split(":")[0]
        labels = entry.get("labels", {})
        if ip not in devices:
            devices[ip] = {"ip": ip, "deviceType": labels.get("device_type", "Unknown"), "regStatus": "online"}

    # batch queries
    node_up_res = _prom_query(prom_url, "up{job!='',instance=~'.*:9100'}")
    jet_up_res = _prom_query(prom_url, "up{job!='',instance=~'.*:9200'}")
    cpu_res = _prom_query(prom_url, "device_cpu_usage_percent{instance=~'.*:9200'}")
    mem_res = _prom_query(prom_url, "device_mem_usage_percent{instance=~'.*:9200'}")
    gpu_res = _prom_query(prom_url, "device_gpu_usage_percent{instance=~'.*:9200'}")
    temp_res = _prom_query(prom_url, "device_temperature_celsius{instance=~'.*:9200'}")
    init_res = _prom_query(prom_url, "device_metrics_initialized{instance=~'.*:9200'}")
    uname_res = _prom_query(prom_url, "node_uname_info{instance=~'.*:9100'}")

    rows = []
    for ip, base in devices.items():
        instance9100 = f"{ip}:9100"
        instance9200 = f"{ip}:9200"
        node_up = _get_value(node_up_res, instance9100) == 1.0 if node_up_res else False
        jet_up = _get_value(jet_up_res, instance9200) == 1.0 if jet_up_res else False
        cpu = _get_value(cpu_res, instance9200)
        mem = _get_value(mem_res, instance9200)
        gpu = _get_value(gpu_res, instance9200)
        temp = _get_value(temp_res, instance9200)
        initialized = _get_value(init_res, instance9200)
        os_info = "Unknown"
        try:
            for item in (uname_res or {}).get("data", {}).get("result", []):
                metric = item.get("metric", {})
                if metric.get("instance") == instance9100:
                    os_info = f"{metric.get('sysname','')}-{metric.get('release','')}".strip("-") or "Unknown"
                    break
        except Exception:
            pass
        status = "online" if (node_up and jet_up) else "offline"
        # 如果设备在注册表标记为offline，优先显示offline
        if base.get("regStatus") == "offline":
            status = "offline"
        def fmt_percent(v):
            try:
                if v is None:
                    return None
                return round(float(v), 2)
            except Exception:
                return None
        def fmt_temp(v):
            try:
                if v is None:
                    return None
                return round(float(v), 1)
            except Exception:
                return None
        rows.append({
            "type": base["deviceType"],
            "ip": ip,
            "temperature": fmt_temp(temp) if initialized else None,
            "memUsage": fmt_percent(mem) if initialized else None,
            "cpuUsage": fmt_percent(cpu) if initialized else None,
            "gpuUsage": fmt_percent(gpu) if initialized else None,
            "status": status,
            "regStatus": base.get("regStatus", "online"),
            "os": os_info,
        })

    return success(data={"items": rows, "total": len(rows)})
