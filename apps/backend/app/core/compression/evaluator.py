import torch
import torch.nn.functional as F
import numpy as np
import joblib
import os
import requests
import json
import threading
import logging
import base64
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from abc import ABC, abstractmethod

# Fix for loading old pickles with newer numpy
# Apply globally on module import
try:
    import numpy.random._pickle
    original_ctor = numpy.random._pickle.__randomstate_ctor
    
    def patched_ctor(bit_generator_name='MT19937', seed=None):
        return original_ctor(bit_generator_name)
        
    numpy.random._pickle.__randomstate_ctor = patched_ctor
    logging.getLogger(__name__).info("Applied numpy.random._pickle.__randomstate_ctor patch for compatibility.")
except Exception as e:
    logging.getLogger(__name__).warning(f"Failed to apply numpy patch: {e}")

logger = logging.getLogger(__name__)

class Evaluator(ABC):
    @abstractmethod
    def evaluate(self, model, prune_rate):
        pass

class AccuracyEvaluator(Evaluator):
    def __init__(self, test_loader, device='cuda'):
        self.test_loader = test_loader
        self.device = device if torch.cuda.is_available() else 'cpu'

    def evaluate(self, model, prune_rate=None):
        model.to(self.device)
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for data, target in self.test_loader:
                data, target = data.to(self.device), target.to(self.device)
                out = model(data)
                pred = out.max(1)[1]
                correct += (pred == target).sum().item()
                total += len(target)
        return correct / total

from app.core.compression.pruner import get_model_layer_sizes

class LatencyEvaluator(Evaluator):
    def __init__(self, base_layer_sizes, base_latency):
        self.base_layer_sizes = np.array(base_layer_sizes)
        self.base_latency = base_latency

    @abstractmethod
    def predict_latency(self, prune_rate):
        pass

    def evaluate(self, model, prune_rate):
        # Calculate global pruning rate from model structure
        current_sizes = get_model_layer_sizes(model)
        
        # Handle dimension mismatch (e.g. if layers dropped out or logic differs)
        if len(current_sizes) != len(self.base_layer_sizes):
            # Fallback to local prune_rate if we can't align
            # Note: this fallback might be wrong for iterative pruning, but better than crash
            return self.predict_latency(prune_rate) / self.base_latency

        # Global Pruning Rate = 1 - (Current / Base)
        # Note: Surrogate models are usually trained on Pruning Rate (0=No Pruning, 1=Full Pruning)
        global_rate = 1.0 - (np.array(current_sizes) / self.base_layer_sizes)
        
        # Predict absolute latency
        lat = self.predict_latency(global_rate)
        
        # Return normalized score
        return lat / self.base_latency

class SurrogateLatencyEvaluator(LatencyEvaluator):
    def __init__(self, model_name, base_layer_sizes, proxy_model_version=None, surrogate_dir='/data/workspace/cluster-compression/benchmarks/surrogate'):
        # Load surrogate models
        self.models = []
        
        # Strategy: Use provided proxy model version if available
        if proxy_model_version and proxy_model_version.file_path:
             path = proxy_model_version.file_path
             if os.path.exists(path):
                 if os.path.isdir(path):
                     # Load all .pkl in dir
                     for f in os.listdir(path):
                        if f.endswith('.pkl'):
                            p = os.path.join(path, f)
                            self.models.append(joblib.load(p))
                 elif path.endswith('.pkl'):
                     self.models.append(joblib.load(path))
                 else:
                     logger.warning(f"Proxy file path {path} is not a directory or .pkl file")
             else:
                 logger.warning(f"Proxy file path {path} does not exist")
        
        # Fallback to default directory naming convention
        if not self.models:
            # Check for specific hardcoded fallback
            hardcoded_path = '/data/workspace/cluster-compression/benchmarks/surrogate/resnet56_latency_model/cluster0-GBRT.pkl'
            if 'resnet56' in model_name.lower() and os.path.exists(hardcoded_path):
                 try:
                     self.models.append(joblib.load(hardcoded_path))
                     logger.info(f"Loaded hardcoded surrogate model from {hardcoded_path}")
                 except Exception as e:
                     logger.warning(f"Failed to load hardcoded surrogate: {e}")

            model_dir = os.path.join(surrogate_dir, f'nano_{model_name}_latency_model')
            if not self.models and os.path.exists(model_dir):
                for f in os.listdir(model_dir):
                    if f.endswith('.pkl'):
                        p = os.path.join(model_dir, f)
                        self.models.append(joblib.load(p))
        
        if not self.models:
            logger.error("No surrogate models loaded. Latency prediction will return 1.0")
        else:
             # Fix sklearn version mismatch for GBR
             for m in self.models:
                 if hasattr(m, 'loss') and not hasattr(m, 'loss_'):
                     if m.loss == 'squared_error':
                         m.loss = 'ls'
                     
                     if m.loss == 'ls':
                         from sklearn.ensemble._gb_losses import LeastSquaresError
                         m.loss_ = LeastSquaresError()

        # Calculate base latency if not provided? 
        # Actually base_latency is needed for normalization.
        # We calculate it from zero-pruning (all zeros)
        # Handle dimension mismatch in init too
        if self.models:
            try:
                # Check features of first model
                m = self.models[0]
                if hasattr(m, 'n_features_in_') and m.n_features_in_ == 1:
                     zeros = np.zeros((1, 1))
                else:
                     zeros = np.zeros((1, len(base_layer_sizes)))
                base_lat = np.mean([m.predict(zeros) for m in self.models])
            except Exception as e:
                logger.warning(f"Failed to calculate base latency: {e}")
                base_lat = 1.0
        else:
            base_lat = 1.0
        
        super().__init__(base_layer_sizes, base_lat)

    def predict_latency(self, prune_rate):
        if not self.models:
            return 1.0
            
        preds = []
        for m in self.models:
            # Handle dimension mismatch
            if hasattr(m, 'n_features_in_') and m.n_features_in_ == 1:
                # Use mean
                feat = np.mean(prune_rate).reshape(1, -1)
            else:
                feat = np.array(prune_rate).reshape(1, -1)
            
            preds.append(m.predict(feat))
            
        return np.mean(preds)

class RemoteLatencyEvaluator(LatencyEvaluator):
    """
    Evaluator that sends the pruning configuration AND the model artifacts (code/weights)
    to a remote device service for real execution.
    """
    def __init__(self, model_name, base_layer_sizes, model_version, device_ip=None, callback_port=9123):
        super().__init__(base_layer_sizes, 1.0)
        
        # Construct device URL from IP if provided
        if device_ip:
            self.device_url = f"http://{device_ip}:11111/submit"
        else:
            self.device_url = "http://localhost:11111/submit"
            
        self.callback_port = callback_port
        self.model_name = model_name
        self.model_version = model_version # Use to get definition and weights path
        
        # Deploy model to device first?
        # Ideally, we upload the model code once.
        # For this implementation, we assume the device service can accept code/weights in the payload 
        # OR we deploy it during initialization.
        self._deploy_model_artifacts()

    def _deploy_model_artifacts(self):
        """
        Reads the model definition file and current weights, and sends them to the device.
        This ensures the device has the correct class definition and base weights to apply pruning.
        """
        logger.info(f"Deploying model artifacts to {self.device_url}...")
        
        # 1. Read Model Definition
        def_content = ""
        if self.model_version.definition_path and os.path.exists(self.model_version.definition_path):
            with open(self.model_version.definition_path, 'r') as f:
                def_content = f.read()
        
        # 2. Read Base Weights (Optional, if device needs base to load)
        # Actually, for latency measurement, random weights might suffice if structure is correct.
        # But 'prune_by_rates' logic on device needs the model structure.
        # We send the definition.
        
        # Payload
        payload = {
            "task": "deploy",
            "model_name": self.model_name,
            "code": def_content,
            # "weights": ... # If needed, base64 encoded.
        }
        
        try:
            # We assume the device has a '/deploy' or similar endpoint, or we handle it in '/submit'
            # Let's assume '/submit' handles deployment if 'code' is present?
            # Or we just send it with every request? (Overhead)
            # Let's try to hit a '/deploy' endpoint or similar if it exists, or just log.
            # Reference implementation assumes model is already there or hardcoded.
            # We will enhance the protocol:
            deploy_url = self.device_url.replace('/submit', '/deploy')
            requests.post(deploy_url, json=payload, timeout=10)
            logger.info("Model artifacts deployed successfully.")
        except Exception as e:
            logger.warning(f"Failed to deploy model artifacts (Device might rely on pre-loaded models): {e}")

    def predict_latency(self, prune_rate):
        return self.measure_remote(prune_rate)

    def measure_remote(self, prune_rate):
        # This path is for search, using prune rates
        data = {
            "pop": [prune_rate.tolist()], # Single individual
            "fn": ["lat"],
            "args": {
                "callback_address": f"http://{self.get_local_ip()}:{self.callback_port}",
                "model": self.model_name,
            }
        }
        return self._send_request_and_wait(data)

    def measure_model_latency(self, model):
        # This path is for final evaluation, sending the whole model state
        
        # Serialize model state_dict
        buffer = io.BytesIO()
        torch.save(model.state_dict(), buffer)
        model_bytes = base64.b64encode(buffer.getvalue()).decode('utf-8')

        data = {
            "fn": ["lat"],
            "args": {
                "callback_address": f"http://{self.get_local_ip()}:{self.callback_port}",
                "model": self.model_name,
                "model_state_dict": model_bytes, # Send serialized state
            }
        }
        return self._send_request_and_wait(data)

    def _send_request_and_wait(self, data):
        # Common logic for sending a request and waiting for a callback

        
        latency_results = []
        event = threading.Event()
        
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                try:
                    msg = json.loads(post_data.decode())
                    if 'metrics' in msg:
                        for m in msg['metrics']:
                            latency_results.append(m['lat'])
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'msg': 'ok', 'status_code': 200}).encode())
                    event.set()
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            def log_message(self, format, *args):
                return # Silence logs

        # Start Server
        server = HTTPServer(('0.0.0.0', 0), Handler)
        self.callback_port = server.server_port
        server_thread = threading.Thread(target=server.handle_request)
        server_thread.start()

        # Send Request
        try:
            requests.post(self.device_url, json=data, timeout=5)
            # Wait for callback
            event.wait(timeout=30)
        except Exception as e:
            logger.error(f"Remote eval failed: {e}")
        
        if latency_results:
            return np.mean(latency_results)
        return float('inf')

    def get_local_ip(self):
        # Hack to get local IP visible to the device
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP
