
import requests
import time
import argparse
import random
import torch
import sys
import os
import threading

# Add backend path to sys.path to import model definition
sys.path.append(os.path.join(os.getcwd(), 'backend/hdap-platform-backend'))
from app.models.definitions.resnet_tiny import resnet56

def simulate_inference_loop(task_id, host='http://localhost:5000', interval=1.0):
    """
    Continuously call the inference API for a Gray Deploy Task.
    Simulates local inference latency of ResNet-Tiny-56 (uncompressed) 
    to make the backend record realistic latency metrics.
    """
    
    url = f"{host}/api/deploy/tasks/{task_id}/inference"
    print(f"Starting continuous simulation for Task ID: {task_id}")
    print(f"Target URL: {url}")
    print(f"Press Ctrl+C to stop...")
    print("-" * 40)

    # 1. Measure Baseline Latency (Local CPU)
    # We run the actual model locally to get a realistic latency baseline
    # which we then "inject" into the API call delay (or just let the API measure wall clock).
    # Wait, the API measures `latency_ms` inside `inference()` function based on `time.sleep()`.
    # And that sleep is based on `ModelVersion.avg_latency_ms` stored in DB.
    # 
    # BUT, the user prompt says: "remember to simulate inference latency also".
    # If the backend `inference` API already simulates latency based on DB, we just need to call it.
    # However, maybe the user wants the client to also wait?
    # Or maybe the backend simulation is too simple (just sleep) and user wants "real" simulation?
    #
    # Let's look at backend logic again:
    # `latency = max(1.0, latency + random.uniform(-5, 10))`
    # `time.sleep(latency / 1000.0)`
    #
    # So the backend *does* simulate latency.
    # We just need to trigger it.
    # 
    # User said: "Backstage doesn't need real deployment... just simulate uncompressed ResNet-Tiny-56 response".
    # This implies we should just call the API repeatedly.
    #
    # However, to be more "realistic" or if we want to control the latency reported:
    # The backend API uses `ModelVersion` latency. If `ModelVersion` has no latency, it uses 50ms default.
    # ResNet-Tiny-56 on CPU might be around 20-50ms depending on hardware.
    # 
    # Let's just call the API in a loop.
    
    # Optional: We can calculate what the real latency *would* be on this machine
    # just for reference.
    try:
        model = resnet56(num_classes=10)
        model.eval()
        dummy_input = torch.randn(1, 3, 32, 32)
        
        # Warmup
        for _ in range(10):
            _ = model(dummy_input)
            
        # Measure
        start = time.time()
        for _ in range(50):
            _ = model(dummy_input)
        avg_latency = (time.time() - start) / 50 * 1000 
        print(f"Measured Local Inference Latency (Reference): {avg_latency:.2f} ms")
    except Exception as e:
        print(f"Could not measure local latency: {e}")

    count = 0
    success_count = 0
    
    while True:
        try:
            # Simulate input (CIFAR-10 image size)
            # Flattened or structured doesn't matter as backend mocks it, 
            # but let's send correct structure.
            payload = {
                "inputs": [[0.1] * 32 * 32 * 3] # Mock data
            }
            
            start_req = time.time()
            resp = requests.post(url, json=payload)
            elapsed = (time.time() - start_req) * 1000
            
            count += 1
            
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                version = data.get('version', 'unknown')
                latency = data.get('latency_ms', 0)
                device_id = data.get('device_id', 'unknown')
                
                print(f"[{time.strftime('%H:%M:%S')}] Req #{count} | Dev: {device_id} | Ver: {version} | Latency: {latency:.1f}ms | Total: {elapsed:.1f}ms")
                success_count += 1
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Req #{count} | Failed: {resp.status_code} - {resp.text}")
                
            # Sleep to control throughput (e.g. 10 QPS = 0.1s interval)
            # Randomize slightly
            sleep_time = max(0.01, interval + random.uniform(-0.1, 0.1))
            time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            print("\nStopping simulation...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Simulate Inference Traffic for Gray Deploy Task')
    parser.add_argument('task_id', type=int, help='Task ID (e.g. 36)')
    parser.add_argument('--host', type=str, default='http://localhost:5000', help='Backend host URL')
    parser.add_argument('--interval', type=float, default=0.2, help='Interval between requests (seconds)')
    
    args = parser.parse_args()
    
    simulate_inference_loop(args.task_id, args.host, args.interval)
