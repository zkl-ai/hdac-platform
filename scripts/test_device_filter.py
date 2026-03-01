
import requests
import time
import argparse
import random
import threading

def test_inference_with_devices(task_id, count=20, host='http://localhost:5000'):
    url = f"{host}/api/deploy/tasks/{task_id}/inference"
    print(f"Starting test for Task ID: {task_id}")
    
    # Send requests
    for i in range(count):
        try:
            resp = requests.post(url, json={"inputs": [[0.1]*32]})
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                print(f"Req {i+1}: Device={data.get('device_id')} Latency={data.get('latency_ms')}")
            else:
                print(f"Req {i+1}: Failed {resp.status_code}")
        except Exception as e:
            print(f"Req {i+1}: Error {e}")
        time.sleep(0.5)

    # Check metrics
    print("\nChecking metrics...")
    metrics_url = f"{host}/api/deploy/tasks/{task_id}/metrics"
    resp = requests.get(metrics_url)
    if resp.status_code == 200:
        data = resp.json().get('data', {})
        devices = data.get('devices', [])
        print(f"Available Devices: {devices}")
        
        if devices:
            target_dev = devices[0]
            print(f"Filtering by device: {target_dev}")
            resp_dev = requests.get(f"{metrics_url}?deviceId={target_dev}")
            data_dev = resp_dev.json().get('data', {})
            print(f"Metrics for {target_dev}: Throughput len={len(data_dev.get('throughput', []))}")
    else:
        print("Failed to get metrics")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('task_id', type=int)
    args = parser.parse_args()
    test_inference_with_devices(args.task_id)
