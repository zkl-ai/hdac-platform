#!/usr/bin/env python3
"""
简单的GPU负载样例：使用PyTorch在CUDA上进行矩阵乘法，产生连续的GPU计算负载。
前置条件：设备已安装CUDA支持的PyTorch。
安装示例：pip3 install torch --extra-index-url https://download.pytorch.org/whl/cu118
"""
import time

def main():
    try:
        import torch
    except Exception as e:
        print("[ERR] PyTorch not available:", e)
        print("Please install torch with CUDA support, e.g.: pip3 install torch --extra-index-url https://download.pytorch.org/whl/cu118")
        return

    if not torch.cuda.is_available():
        print("[ERR] CUDA is not available on this device.")
        return

    dev = torch.device("cuda")
    print("[OK] Using", torch.cuda.get_device_name(0))

    # 准备大尺寸张量以产生负载
    size = 2048
    a = torch.randn((size, size), device=dev)
    b = torch.randn((size, size), device=dev)

    # 预热
    for _ in range(5):
        _ = torch.mm(a, b)
        torch.cuda.synchronize()

    print("[RUN] GPU stress started. Running matmul loops...")
    t0 = time.time()
    iters = 0
    try:
        while time.time() - t0 < 30:  # 运行30秒
            _ = torch.mm(a, b)
            torch.cuda.synchronize()
            iters += 1
            if iters % 50 == 0:
                print("[RUN] iterations:", iters)
    except KeyboardInterrupt:
        pass
    print("[DONE] Completed iterations:", iters)

if __name__ == "__main__":
    main()

