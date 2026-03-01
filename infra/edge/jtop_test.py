#!/usr/bin/env python3
import time

def main():
    try:
        from jtop import jtop
    except Exception as e:
        print("[ERR] cannot import jtop:", e)
        print("Please install jetson-stats: sudo -H pip3 install -U jetson-stats")
        return

    try:
        with jtop() as jetson:
            print("[OK] jtop started, interval:", getattr(jetson, 'interval', 'unknown'))
            # wait until ready
            t0 = time.time()
            while not jetson.ok():
                time.sleep(0.5)
                if time.time() - t0 > 10:
                    print("[WARN] jtop not ready after 10s, continue")
                    break

            debug_printed = False
            for i in range(10):
                # CPU
                cpu_pct = None
                try:
                    c = getattr(jetson, 'cpu', {}) or {}
                    tot = c.get('total') or {}
                    idle = tot.get('idle')
                    if idle is not None:
                        cpu_pct = max(0.0, 100.0 - float(idle))
                    else:
                        u = float(tot.get('user', 0.0))
                        s = float(tot.get('system', 0.0))
                        n = float(tot.get('nice', 0.0))
                        cpu_pct = u + s + n
                except Exception:
                    cpu_pct = None

                # GPU
                gpu_pct = None
                try:
                    def read_gpu_load(g):
                        st = g.get('status')
                        if isinstance(st, dict):
                            v = st.get('load')
                            try:
                                return float(v) if v is not None and float(v) == float(v) else None
                            except Exception:
                                return None
                            print("load", v)
                        gv = g.get('gv11b')
                        if isinstance(gv, dict):
                            s = gv.get('status')
                            if isinstance(s, dict):
                                v = s.get('load')
                                try:
                                    return float(v) if v is not None and float(v) == float(v) else None
                                except Exception:
                                    return None
                        return None

                    g = getattr(jetson, 'gpu', None)
                    print(g)
                    gpu_pct = read_gpu_load(g)
                except Exception:
                    gpu_pct = None
                if gpu_pct is None and not debug_printed:
                    print('[DBG] jetson.gpu=', getattr(jetson, 'gpu', None))
                    debug_printed = True

                # Memory via memory.RAM (values in KB)
                mem_pct = None
                try:
                    mem = getattr(jetson, 'memory', {}) or {}
                    ram = mem.get('RAM') or {}
                    used = ram.get('used')
                    total = ram.get('tot')
                    if used is not None and total is not None:
                        uf = float(used)
                        tf = float(total)
                        mem_pct = uf / (tf if tf != 0 else 1.0) * 100.0
                    else:
                        # fallback to legacy ram structure
                        r = getattr(jetson, 'ram', {}) or {}
                        def v(x):
                            if isinstance(x, dict):
                                return x.get('value', x.get('VAL', x.get('val', x.get('VALUE'))))
                            return x
                        used = v(r.get('used') or r.get('use') or r.get('USED'))
                        total = v(r.get('total') or r.get('tot') or r.get('TOTAL'))
                        if used is not None and total is not None:
                            uf = float(used)
                            tf = float(total)
                            mem_pct = uf / (tf if tf != 0 else 1.0) * 100.0
                except Exception:
                    mem_pct = None

                # Temperature
                tcpu = None
                tgpu = None
                try:
                    t = getattr(jetson, 'temperature', {}) or {}
                    def temp_val(x):
                        if isinstance(x, dict):
                            # e.g. { temp: 42.0, online: True }
                            return x.get('temp', x.get('TEMP'))
                        return x
                    tcpu = temp_val(t.get('CPU') or t.get('TCPU') or t.get('cpu'))
                    tgpu = temp_val(t.get('GPU') or t.get('TGPU') or t.get('gpu'))
                    if tcpu is not None:
                        tcpu = float(tcpu)
                    if tgpu is not None:
                        tgpu = float(tgpu)
                except Exception:
                    pass

                print(f"CPU={cpu_pct if cpu_pct is not None else 'n/a'}% | GPU={gpu_pct if gpu_pct is not None else 'n/a'}% | MEM={mem_pct if mem_pct is not None else 'n/a'}% | TCPU={tcpu if tcpu is not None else 'n/a'}C | TGPU={tgpu if tgpu is not None else 'n/a'}C")
                time.sleep(1)

    except Exception as e:
        print("[ERR] jtop test failure:", e)

if __name__ == '__main__':
    main()
