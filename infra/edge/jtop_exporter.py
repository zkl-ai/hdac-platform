import time
import subprocess
import re
from prometheus_client import Gauge, start_http_server

cpu_usage = Gauge("device_cpu_usage_percent", "CPU usage percent")
gpu_usage = Gauge("device_gpu_usage_percent", "GPU usage percent")
mem_usage = Gauge("device_mem_usage_percent", "Memory usage percent")
temp_cpu = Gauge("device_temperature_celsius", "CPU temperature celsius")
temp_gpu = Gauge("device_gpu_temperature_celsius", "GPU temperature celsius")
initialized = Gauge("device_metrics_initialized", "1 if metrics parsed at least once")

def run_jtop_loop():
    from jtop import jtop
    with jtop() as jetson:
        while not jetson.ok():
            time.sleep(0.5)
        initialized.set(1)
        zero = 0
        while True:
            try:
                cpu = 0.0
                try:
                    c = getattr(jetson, "cpu", {}) or {}
                    tot = c.get("total") or {}
                    idle = tot.get("idle")
                    if idle is not None:
                        cpu = max(0.0, 100.0 - float(idle))
                    else:
                        u = float(tot.get("user", 0.0))
                        s = float(tot.get("system", 0.0))
                        n = float(tot.get("nice", 0.0))
                        cpu = u + s + n
                except Exception:
                    cpu = 0.0
                cpu_usage.set(cpu)

                gpu = 0.0
                try:
                    g = getattr(jetson, "gpu", None)
                    st = None
                    try:
                        st = g.get("status")
                    except Exception:
                        st = None
                    if isinstance(st, dict):
                        val = st.get("load")
                        if val is not None:
                            try:
                                x = float(val)
                                if x == x:
                                    gpu = x
                            except Exception:
                                gpu = 0.0
                    gv = None
                    try:
                        gv = g.get("gv11b")
                    except Exception:
                        gv = None
                    if isinstance(gv, dict):
                        s = gv.get("status")
                        if isinstance(s, dict):
                            val = s.get("load")
                            if val is not None:
                                try:
                                    x = float(val)
                                    if x == x:
                                        gpu = x
                                except Exception:
                                    gpu = 0.0
                except Exception:
                    gpu = 0.0
                gpu_usage.set(gpu)

                mp = 0.0
                try:
                    mem = getattr(jetson, "memory", {}) or {}
                    ram = mem.get("RAM") or {}
                    used = ram.get("used")
                    total = ram.get("tot")
                    if used is not None and total is not None:
                        uf = float(used)
                        tf = float(total)
                        mp = uf / (tf if tf != 0 else 1.0) * 100.0
                    else:
                        r = getattr(jetson, "ram", {}) or {}
                        used = r.get("used") or r.get("use") or r.get("USED")
                        total = r.get("total") or r.get("tot") or r.get("TOTAL")
                        if used is not None and total is not None:
                            uf = float(used)
                            tf = float(total)
                            mp = uf / (tf if tf != 0 else 1.0) * 100.0
                except Exception:
                    mp = 0.0
                mem_usage.set(mp)

                try:
                    t = getattr(jetson, "temperature", {}) or {}
                    def _tv(x):
                        if isinstance(x, dict):
                            return x.get("temp")
                        return x
                    tcpu = _tv(t.get("CPU") or t.get("TCPU") or t.get("cpu"))
                    tgpu = _tv(t.get("GPU") or t.get("TGPU") or t.get("gpu"))
                    if tcpu is not None:
                        temp_cpu.set(float(tcpu))
                    if tgpu is not None:
                        temp_gpu.set(float(tgpu))
                except Exception:
                    pass
                if cpu == 0.0 and gpu == 0.0 and mp == 0.0:
                    zero += 1
                else:
                    zero = 0
                if zero >= 20:
                    raise RuntimeError("fallback")
            except Exception:
                pass
            time.sleep(0.5)

def parse_tegrastats(line):
    cpu = 0.0
    m = re.search(r"CPU\[(.*?)\]", line)
    if m:
        parts = re.findall(r"(\d+)\%", m.group(1))
        if parts:
            vals = [float(p) for p in parts]
            cpu = sum(vals) / len(vals)
    gpu = 0.0
    mg = re.search(r"GR3D_FREQ\s+(\d+)\%", line)
    if mg:
        gpu = float(mg.group(1))
    mp = 0.0
    mm = re.search(r"RAM\s+(\d+)/(\d+)MB", line)
    if mm:
        try:
            used = float(mm.group(1))
            total = float(mm.group(2))
            if total != 0:
                mp = used / total * 100.0
        except Exception:
            mp = 0.0
    tcpu = None
    tgpu = None
    mtcpu = re.search(r"CPU@?(\d+)C", line) or re.search(r"TCPU\s*:\s*(\d+)\s*C", line)
    mtgpu = re.search(r"GPU@?(\d+)C", line) or re.search(r"TGPU\s*:\s*(\d+)\s*C", line)
    if mtcpu:
        tcpu = float(mtcpu.group(1))
    if mtgpu:
        tgpu = float(mtgpu.group(1))
    return cpu, gpu, mp, tcpu, tgpu

def run_tegrastats_loop():
    p = subprocess.Popen(["tegrastats", "--interval", "1000"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
    initialized.set(1)
    while True:
        line = p.stdout.readline()
        if not line:
            time.sleep(0.5)
            continue
        cpu, gpu, mp, tcpu, tgpu = parse_tegrastats(line)
        cpu_usage.set(cpu)
        gpu_usage.set(gpu)
        mem_usage.set(mp)
        if tcpu is not None:
            temp_cpu.set(tcpu)
        if tgpu is not None:
            temp_gpu.set(tgpu)
        time.sleep(0.5)

def main():
    start_http_server(9200)
    try:
        run_jtop_loop()
    except Exception:
        try:
            run_tegrastats_loop()
        except Exception:
            while True:
                time.sleep(1)

if __name__ == "__main__":
    main()
