
import time
import torch
import torch_pruning as tp
import sys
import os
import io

# Add path
sys.path.append(os.getcwd())

from app.models.definitions.resnet_tiny import resnet56
from app.core.compression.pruner import ModelPruner

def benchmark_v2():
    print("--- Benchmark V2: Server-side vs Edge-side Simulation ---")
    
    # Setup
    device = torch.device('cpu')
    model = resnet56(num_classes=10)
    model.to(device)
    model.eval()
    example_input = torch.randn(1, 3, 32, 32).to(device)
    
    # 1. Measure Pruning Compute Time (Server)
    # This represents the "Server Compute" in Workflow 2
    # And we can estimate Edge Compute (Workflow 1) by multiplying this by ~5-8x (Jetson NX CPU factor)
    
    print("\n[Phase 1] Measuring Pruning Compute (Server CPU)...")
    t0 = time.time()
    
    # Initialize Pruner (Builds Dependency Graph - Expensive)
    pruner = ModelPruner(model, example_input)
    t_init = time.time() - t0
    
    # Prune (Execute Pruning - Moderate)
    # Prune 50% of channels
    rates = [0.5] * 30 
    t1 = time.time()
    pruned_model = pruner.prune_by_rates(rates)
    t_step = time.time() - t1
    
    total_prune_server = t_init + t_step
    print(f"  Graph Build Time: {t_init*1000:.2f} ms")
    print(f"  Pruning Step Time: {t_step*1000:.2f} ms")
    print(f"  Total Server Pruning Time: {total_prune_server*1000:.2f} ms")
    
    # Estimate Edge Pruning Time
    # Jetson Xavier NX (Carmel ARM) vs Server (Xeon/Core).
    # Single core performance gap is significant for Python.
    edge_slowdown_factor = 6.0 
    estimated_edge_prune = total_prune_server * edge_slowdown_factor
    print(f"  (Est.) Edge Pruning Time (x{edge_slowdown_factor}): {estimated_edge_prune*1000:.2f} ms")

    # 2. Measure Model Serialization (Transmission Payload)
    # This represents the payload for Workflow 2
    
    print("\n[Phase 2] Measuring Model Serialization...")
    buffer = io.BytesIO()
    t2 = time.time()
    torch.save(pruned_model, buffer)
    t_save = time.time() - t2
    size_bytes = buffer.tell()
    size_mb = size_bytes / (1024 * 1024)
    
    print(f"  Serialized Model Size: {size_mb:.2f} MB")
    print(f"  Save Time: {t_save*1000:.2f} ms")
    
    # Estimate Transmission Time
    # Wifi (30 Mbps) vs LAN (100 Mbps)
    # 30 Mbps = 3.75 MB/s
    # 100 Mbps = 12.5 MB/s
    tx_time_wifi = size_mb / 3.75
    tx_time_lan = size_mb / 12.5
    print(f"  (Est.) TX Time (WiFi 30Mbps): {tx_time_wifi*1000:.2f} ms")
    print(f"  (Est.) TX Time (LAN 100Mbps): {tx_time_lan*1000:.2f} ms")
    
    # 3. Measure Model Load Time
    # This represents Edge Loading in Workflow 2
    buffer.seek(0)
    t3 = time.time()
    loaded_model = torch.load(buffer, weights_only=False)
    t_load = time.time() - t3
    print(f"  Load Time (Server): {t_load*1000:.2f} ms")
    
    # Estimate Edge Load Time
    # I/O or Memory bound, maybe 2-3x slower
    edge_load_factor = 3.0
    estimated_edge_load = t_load * edge_load_factor
    print(f"  (Est.) Edge Load Time (x{edge_load_factor}): {estimated_edge_load*1000:.2f} ms")
    
    # 4. Summary Comparison
    print("\n[Summary Comparison]")
    
    # Workflow 1: Edge Pruning
    # Time = Edge_Prune
    w1_time = estimated_edge_prune
    print(f"Workflow 1 (Edge Pruning): ~{w1_time*1000:.0f} ms")
    
    # Workflow 2: Server Pruning
    # Time = Server_Prune + TX + Edge_Load
    # Using WiFi as conservative network
    w2_time_wifi = total_prune_server + tx_time_wifi + estimated_edge_load
    w2_time_lan = total_prune_server + tx_time_lan + estimated_edge_load
    
    print(f"Workflow 2 (Server Pruning + WiFi): ~{w2_time_wifi*1000:.0f} ms")
    print(f"Workflow 2 (Server Pruning + LAN):  ~{w2_time_lan*1000:.0f} ms")

if __name__ == "__main__":
    benchmark_v2()
