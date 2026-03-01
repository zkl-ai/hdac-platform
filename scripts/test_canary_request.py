import requests
import time
import argparse
import random

def test_inference(task_id, count=10, interval=1.0, host='http://localhost:5000'):
    url = f"{host}/api/deploy/tasks/{task_id}/inference"
    print(f"Starting test for Task ID: {task_id}")
    print(f"Target URL: {url}")
    print(f"Count: {count}, Interval: {interval}s")
    print("-" * 40)

    # Simulate input tensor (1, 3, 32, 32) flattened or nested list
    # Just sending a small dummy payload for MVP
    dummy_input = {
        "inputs": [[0.1] * 32] * 32 # Simplified dummy input
    }

    success_count = 0
    candidate_count = 0
    
    for i in range(count):
        try:
            start = time.time()
            resp = requests.post(url, json=dummy_input)
            elapsed = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                version = data.get('version', 'unknown')
                latency = data.get('latency_ms', 0)
                
                print(f"[{i+1}/{count}] Status: {resp.status_code} | Version: {version:<10} | Latency: {latency:>6.2f}ms | Overhead: {elapsed - latency:>6.2f}ms")
                
                success_count += 1
                if version == 'candidate':
                    candidate_count += 1
            else:
                print(f"[{i+1}/{count}] Failed: {resp.status_code} - {resp.text}")
                
        except Exception as e:
            print(f"[{i+1}/{count}] Error: {e}")
            
        if i < count - 1:
            time.sleep(interval)

    print("-" * 40)
    print(f"Summary:")
    print(f"Total Requests: {count}")
    print(f"Successful:     {success_count}")
    print(f"Candidate Ratio: {candidate_count}/{success_count} ({candidate_count/success_count*100:.1f}%)" if success_count > 0 else "Ratio: N/A")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test Gray Deployment Inference API')
    parser.add_argument('task_id', type=int, help='ID of the gray deploy task')
    parser.add_argument('--count', type=int, default=20, help='Number of requests to send')
    parser.add_argument('--interval', type=float, default=0.5, help='Interval between requests (seconds)')
    parser.add_argument('--host', type=str, default='http://localhost:5000', help='Backend host URL')
    
    args = parser.parse_args()
    
    test_inference(args.task_id, args.count, args.interval, args.host)
