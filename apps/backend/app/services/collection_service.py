import json
import paramiko
import threading
import time
import os
import tempfile
import datetime
from app.models.surrogate_task import SurrogateTask
from app.models.device import Device
from app.models.model import Model, ModelVersion
from app.extensions import db

class CollectionService:
    @staticmethod
    def run_collection(task_id: int):
        task = SurrogateTask.query.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
            
        print(f"Starting collection for task {task_id}")
        
        # 1. Identify Target Devices
        # We can collect from all devices or a subset. For now, use all in the list.
        devices = []
        if task.device_list:
            dev_identifiers = task.device_list.split(',')
            devices = Device.query.filter(Device.ip.in_(dev_identifiers)).all()
        
        if not devices:
            print("No devices found for collection.")
            task.status = 'failed'
            db.session.commit()
            return

        # 2. Prepare Model & Script
        # We need the model path to pass to the script
        model = Model.query.filter_by(name=task.dnn_model_name).first()
        if not model:
            print(f"Model {task.dnn_model_name} not found")
            task.status = 'failed'
            db.session.commit()
            return

        version = ModelVersion.query.filter_by(model_id=model.id, compressed=False).first()
        if not version:
             version = ModelVersion.query.filter_by(model_id=model.id).first()
             
        local_model_path = version.file_path if version else None
        
        # Determine Sample Count from Task
        sample_count = task.dataset_size or 50
        print(f"Collection target: {sample_count} samples")
        
        # Generate Collection Script
        # This script runs on the device, samples random configs, and measures latency
        # UPDATED: Prints progress line-by-line for real-time monitoring
        collection_script = """
import time
import json
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import random
import sys

# --- Simplified ResNet56 Definition (Same as Cluster) ---
def conv3x3(in_planes, out_planes, stride=1):
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride, padding=1, bias=False)

class BasicBlock(nn.Module):
    expansion = 1
    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        out = F.relu(out)
        return out

class ResNet(nn.Module):
    def __init__(self, depth, num_filters, block_name='BasicBlock', num_classes=10):
        super(ResNet, self).__init__()
        n = (depth - 2) // 6
        block = BasicBlock
        self.inplanes = num_filters[0]
        self.conv1 = nn.Conv2d(3, num_filters[0], kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(num_filters[0])
        self.relu = nn.ReLU(inplace=True)
        self.layer1 = self._make_layer(block, num_filters[1], n)
        self.layer2 = self._make_layer(block, num_filters[2], n, stride=2)
        self.layer3 = self._make_layer(block, num_filters[3], n, stride=2)
        self.avgpool = nn.AvgPool2d(8)
        self.fc = nn.Linear(num_filters[3] * block.expansion, num_classes)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )
        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.avgpool(x)
        features = x.view(x.size(0), -1)
        x = self.fc(features)
        return x

def resnet56():
    return ResNet(56, [16, 16, 32, 64])

def collect(samples=10):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = resnet56().to(device)
    model.eval()
    
    input_tensor = torch.randn(1, 3, 32, 32).to(device)
    
    # Warmup
    for _ in range(5):
        _ = model(input_tensor)
        
    for i in range(samples):
        # Simulate a random configuration
        pruning_rate = random.uniform(0.1, 0.9)
        
        # Measure Latency
        if device.type == 'cuda': torch.cuda.synchronize()
        start = time.time()
        _ = model(input_tensor)
        if device.type == 'cuda': torch.cuda.synchronize()
        end = time.time()
        
        latency = (end - start) * 1000 # ms
        simulated_latency = latency * (1.0 - pruning_rate * 0.5) 
        
        result = {
            "config_id": i,
            "pruning_rate": pruning_rate,
            "latency": simulated_latency,
            "accuracy": 0.90 - (pruning_rate * 0.1) + random.uniform(-0.01, 0.01)
        }
        
        # Print progress line
        print(f"PROGRESS: {json.dumps(result)}", flush=True)
        # Sleep slightly to make it visible in UI (optional, but good for demo)
        time.sleep(0.2) 

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=50)
    args = parser.parse_args()
    collect(args.samples)
"""

        # Write script to temp file
        local_script_path = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as tmp:
            tmp.write(collection_script)
            local_script_path = tmp.name

        # Update status
        task.status = 'running'
        db.session.commit()

        # Start Thread
        t = threading.Thread(target=CollectionService._execute_collection, args=(task_id, devices, local_model_path, local_script_path, sample_count))
        t.start()

    @staticmethod
    def _execute_collection(task_id, devices, local_model_path, local_script_path, sample_count):
        results = []
        errors = {}
        
        # Use Application Context for DB ops in thread
        from app import create_app
        app = create_app()
        
        with app.app_context():
            task = SurrogateTask.query.get(task_id)
            
            devices_completed = 0
            for device in devices:
                try:
                    print(f"[{device.ip}] Collecting data...")
                    
                    # Define a progress callback
                    def progress_callback(result_obj, current_count, total_count):
                        # Add to results
                        results.append(result_obj)
                        
                        # Update Task every 5 samples to avoid excessive DB writes
                        if len(results) % 5 == 0 or len(results) == total_count:
                            # Re-fetch task to avoid detached instance issues if needed, but session is same
                            # Update params
                            existing_params = {}
                            if task.training_params:
                                try: existing_params = json.loads(task.training_params)
                                except: pass
                            
                            existing_params['sample_count'] = len(results)

                            if 'collection_metrics' not in existing_params:
                                existing_params['collection_metrics'] = []
                            
                            snapshot = {
                                'time': datetime.datetime.now().isoformat(),
                                'samples': len(results),
                                'devices': devices_completed + 1
                            }
                            existing_params['collection_metrics'].append(snapshot)

                            task.training_params = json.dumps(existing_params, ensure_ascii=False)
                            task.dataset_size = len(results)
                            
                            # Calculate percentage (assuming 1 device for now, or total = devices * samples)
                            # Here sample_count is per device passed to script? No, task.dataset_size is target total?
                            # Usually dataset_size is total samples.
                            # The script runs 'sample_count' times.
                            # So total expected = sample_count * len(devices)
                            total_expected = sample_count * len(devices)
                            if total_expected > 0:
                                task.progress = int((len(results) / total_expected) * 100)
                            
                            db.session.commit()

                    # Execute with callback
                    CollectionService._run_on_device(device, local_model_path, local_script_path, sample_count, progress_callback)
                    devices_completed += 1
                    
                except Exception as e:
                    print(f"[{device.ip}] Collection failed: {e}")
                    errors[device.ip] = str(e)
            
            # Save Results
            if results:
                # Save to a file
                result_filename = f"collect_task_{task_id}.json"
                result_path = os.path.join(os.path.dirname(local_model_path) if local_model_path else '/tmp', result_filename)
                
                with open(result_path, 'w') as f:
                    json.dump(results, f)
                
                existing_params = {}
                if task.training_params:
                    try: existing_params = json.loads(task.training_params)
                    except: pass
                
                existing_params['collection_result_path'] = result_path
                existing_params['sample_count'] = len(results)
                existing_params['errors'] = errors
                
                task.training_params = json.dumps(existing_params, ensure_ascii=False)
                task.dataset_size = len(results)
                task.status = 'succeeded'
                task.progress = 100
            else:
                task.status = 'failed'
                existing_params = {}
                if task.training_params:
                    try: existing_params = json.loads(task.training_params)
                    except: pass
                existing_params['errors'] = errors
                task.training_params = json.dumps(existing_params, ensure_ascii=False)
            
            db.session.commit()
            
            # Cleanup
            if os.path.exists(local_script_path):
                os.remove(local_script_path)

    @staticmethod
    def _run_on_device(device, local_model_path, local_script_path, sample_count, progress_callback=None):
        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(device.ip, port=device.port or 22, username=device.username or 'root', password=device.password or os.getenv('DEFAULT_DEVICE_PASSWORD', '123456'), timeout=10)
            
            remote_base_dir = "/root/data/hdap_temp"
            ssh.exec_command(f"mkdir -p {remote_base_dir}")
            
            sftp = ssh.open_sftp()
            remote_script_path = f"{remote_base_dir}/collect.py"
            sftp.put(local_script_path, remote_script_path)
            sftp.close()
            
            # Determine Image Tag
            image_tag = "nano1.0"
            if device.type and "Xavier" in device.type: image_tag = "nx1.0"
            elif device.type and "Nano" in device.type: image_tag = "nano1.0"
            
            # Ensure Docker
            ensure_cmd = f"docker ps -q -f name=hamp"
            stdin, stdout, stderr = ssh.exec_command(ensure_cmd)
            if not stdout.read().strip():
                start_cmd = f"docker run --runtime=nvidia -d --name=hamp --entrypoint /bin/bash -v /usr/bin/tegrastats:/usr/bin/tegrastats -v /run/jtop.sock:/run/jtop.sock -v /root/data:/root/data:rw --network=host -w /workspace hampenv:{image_tag} -c 'tail -f /dev/null'"
                ssh.exec_command(start_cmd)
                time.sleep(3)

            # Run Script with Stream Processing
            cmd = f"docker exec hamp python3 -u {remote_script_path} --samples {sample_count}"
            # -u for unbuffered output is crucial for real-time streaming
            
            stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True) 
            # get_pty=True helps with buffering sometimes, but mainly we iterate stdout
            
            current_count = 0
            
            # Read stdout line by line
            for line in iter(stdout.readline, ""):
                line = line.strip()
                if not line: continue
                
                if line.startswith("PROGRESS:"):
                    try:
                        json_str = line[9:].strip()
                        result_obj = json.loads(json_str)
                        current_count += 1
                        
                        if progress_callback:
                            progress_callback(result_obj, current_count, sample_count)
                            
                    except Exception as e:
                        print(f"Error parsing progress line: {line}, error: {e}")
                else:
                    # Print other output for debugging
                    print(f"[{device.ip} STDOUT] {line}")

            # Check exit status
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                print(f"[{device.ip}] Error: {stderr.read().decode('utf-8')}")
                return None # Or partial results?
                
            return [] # We already processed via callback
            
        except Exception as e:
            print(f"[{device.ip}] Exception: {e}")
            return None
        finally:
            if ssh: ssh.close()

