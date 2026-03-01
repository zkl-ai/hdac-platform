from datetime import datetime
import os
import torch
import json
import logging
import time
import inspect
from app.extensions import db
from app.models.compress_task import CompressTask, CompressStage
from app.models.model import ModelVersion
from app.core.compression.loader import ModelLoader
from app.core.compression.pruner import ModelPruner
from app.core.compression.data_utils import get_dataloader
from app.core.compression.evaluator import AccuracyEvaluator, SurrogateLatencyEvaluator, RemoteLatencyEvaluator
from app.core.compression.search_strategy import EvolutionarySearch

logger = logging.getLogger(__name__)

class CompressionPipeline:
    def __init__(self, task_id):
        self.task_id = task_id
        self.task = CompressTask.query.get(task_id)
        if not self.task:
            raise ValueError(f"Task {task_id} not found")
        
        # Setup output dir
        self.output_dir = f'/data/workspace/hdap-platform/backend/hdap-platform-backend/data/tasks/{self.task_id}'
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Parse Params
        self.params = self._parse_params()

        # Load Model
        logger.info(f"Loading model for task {self.task.name}...")
        load_res = ModelLoader.load_model_instance(self.task.model_name, self.task.device_type)
        if isinstance(load_res, tuple) and len(load_res) == 3:
            self.model, self.model_version, self.custom_components = load_res
        else:
            self.model, self.model_version = load_res
            self.custom_components = {}
        
        # Load Data
        dataset_name = self.model_version.dataset or 'cifar10'
        logger.info(f"Loading dataset {dataset_name}...")
        
        if 'get_dataloader' in self.custom_components:
                 # Resolve args
                 func = self.custom_components['get_dataloader']
                 sig = inspect.signature(func)
                 args = {}
                 
                 context = {
                     'dataset_name': dataset_name,
                     'batch_size': int(self.params.get('batch_size', 64))
                 }
                 
                 for param_name in sig.parameters:
                    if param_name in context:
                        args[param_name] = context[param_name]
                    elif param_name in self.params:
                        args[param_name] = self.params[param_name]

                 # Call
                 self.train_loader, self.test_loader, self.num_classes, self.input_size = func(**args)
        else:
            self.train_loader, self.test_loader, self.num_classes, self.input_size = get_dataloader(dataset_name)
        
        # Init Pruner
        # Create example input
        # Fix: ResNet-Tiny on CIFAR expects input size [1, 3, 32, 32]
        # self.input_size is usually a tuple (3, 32, 32).
        # torch.randn(1, *self.input_size) creates [1, 3, 32, 32] which is correct 4D batched input.
        # But if self.input_size is already batched like (1, 3, 32, 32), then we get 5D.
        
        # Ensure self.input_size is unbatched (C, H, W)
        if len(self.input_size) == 4:
            self.input_size = self.input_size[1:]
        
        # Setup Device
        self.device = self._get_device()
        if self.device.type == 'cuda':
            torch.cuda.set_device(self.device)
        logger.info(f"Using device: {self.device}")
        self.model.to(self.device)
            
        example_input = torch.randn(1, *self.input_size).to(self.device)
        
        # Load pruning config (base layer sizes)
        self.current_layer_sizes = ModelLoader.get_pruning_config(self.task.model_name)
        
        self.pruner = ModelPruner(self.model, example_input, layer_sizes=self.current_layer_sizes)
        
    def _parse_params(self):
        # Find pruning stage
        stage = CompressStage.query.filter_by(task_id=self.task.id, phase='pruning').first()
        params = {}
        if stage and stage.algo_params:
            try:
                if stage.algo_params.startswith('{'):
                    params = json.loads(stage.algo_params)
                else:
                    for p in stage.algo_params.split(';'):
                        if '=' in p:
                            k, v = p.split('=')
                            params[k.strip()] = v.strip()
            except Exception as e:
                logger.error(f"Error parsing params: {e}")
        
        # Merge with task info
        params['method'] = stage.compression_algo if stage else 'HDAP'
        if stage:
            if stage.accuracy_loss_limit is not None:
                params['accuracy_constraint'] = float(stage.accuracy_loss_limit)
            if stage.latency_budget is not None:
                params['latency_budget'] = float(stage.latency_budget)
        
        # Defaults
        params.setdefault('train_epochs', 5)
        params.setdefault('batch_size', 64)
        params.setdefault('lr', 0.01)
        
        return params

    def _init_evaluators(self):
        evaluators = {}
        # Accuracy
        evaluators['accuracy'] = AccuracyEvaluator(self.test_loader)
        
        # Latency
        base_layer_sizes = self.pruner.get_layer_sizes()
        
        use_proxy = self.params.get('use_proxy', 'False') == 'True'
        if use_proxy:
            proxy_model_name = self.params.get('proxy_model')
            proxy_model_version = None
            if proxy_model_name:
                proxy_model_version = ModelVersion.query.filter_by(name=proxy_model_name).first()
                if not proxy_model_version:
                    logger.warning(f"Proxy model {proxy_model_name} not found in DB")
            
            logger.info(f"Using Surrogate Evaluator with proxy: {proxy_model_name}")
            evaluators['latency'] = SurrogateLatencyEvaluator(
                self.task.model_name, 
                base_layer_sizes, 
                proxy_model_version=proxy_model_version
            )
        else:
            # Check if we should use Remote (Real Device)
            if self.task.device_type:
                logger.info(f"Using Remote Evaluator for {self.task.device_type}")
                # We assume the device server URL is configured or standard
                # Pass model_version to allow code deployment
                evaluators['latency'] = RemoteLatencyEvaluator(
                    self.task.model_name, 
                    base_layer_sizes, 
                    self.model_version
                )
            else:
                logger.warning("No device type and no proxy. Using Surrogate as fallback.")
                evaluators['latency'] = SurrogateLatencyEvaluator(self.task.model_name, base_layer_sizes)
                
        return evaluators

    def _log_metric(self, phase, step, data):
        """
        Log metrics to metrics.json
        data: dict of metrics (e.g. {'loss': 0.5, 'accuracy': 80.0})
        """
        metric_file = os.path.join(self.output_dir, 'metrics.json')
        
        # Convert numpy types to native types and handle NaN/Inf
        def convert(obj):
            import math
            if isinstance(obj, (np.integer, np.floating, np.bool_)):
                obj = obj.item()
            
            if isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj
            
        import numpy as np
        data = {k: convert(v) for k, v in data.items()}
        
        entry = {
            'timestamp': time.time(),
            'phase': phase, # 'search', 'finetune', 'pruning_iter'
            'step': step,
            **data
        }
        
        # Append to file in a robust way
        try:
            # We use append mode with a list structure is tricky.
            # Better to read, append, write.
            if os.path.exists(metric_file):
                with open(metric_file, 'r') as f:
                    try:
                        metrics = json.load(f)
                        if not isinstance(metrics, list): metrics = []
                    except:
                        metrics = []
            else:
                metrics = []
                
            metrics.append(entry)
            
            with open(metric_file, 'w') as f:
                json.dump(metrics, f)
        except Exception as e:
            logger.error(f"Failed to log metric: {e}")

    def _get_device(self):
        # Prioritize config param
        if 'device' in self.params:
            return torch.device(self.params['device'])
            
        # Restriction: Only use GPU 7
        target_gpu_index = 7
        
        if torch.cuda.is_available():
            if torch.cuda.device_count() > target_gpu_index:
                logger.info(f"Using restricted GPU: cuda:{target_gpu_index}")
                return torch.device(f'cuda:{target_gpu_index}')
            else:
                logger.warning(f"Restricted GPU {target_gpu_index} requested but not available (count={torch.cuda.device_count()}). Falling back to cpu.")
                # If we can't get the restricted GPU, we fallback to CPU to avoid interfering with others (0-6).
                return torch.device('cpu')
                
        return torch.device('cpu')

    def run(self):
        logger.info("Pipeline started.")
        
        self.evaluators = self._init_evaluators()
        
        # Determine strategy
        method = self.params.get('method', 'HDAP')
        
        if method == 'HDAP':
            self._run_hdap(self.evaluators)
        else:
            self._run_grid_search(self.evaluators)
            
        # Register the final model to the library
        self._register_model()
            
        logger.info("Pipeline completed.")

    def _register_model(self):
        """Register the compressed model to the Model Library (DB)"""
        
        final_latency_ms = None
        
        # Final Real-Device Evaluation on a list of IPs
        # The user provides this in the 'pruning' stage params as 'device_ips'
        device_ips_str = self.params.get('device_ips')
        
        if device_ips_str:
            device_ips = [ip.strip() for ip in device_ips_str.split(',') if ip.strip()]
            all_latencies = []
            
            logger.info(f"Performing final real-device evaluation on {len(device_ips)} devices...")
            
            for device_ip in device_ips:
                logger.info(f"  - Evaluating on device: {device_ip}")
                try:
                    real_evaluator = RemoteLatencyEvaluator(
                        self.task.model_name,
                        self.pruner.get_layer_sizes(),
                        self.model_version,
                        device_ip=device_ip
                    )
                    latency = real_evaluator.measure_model_latency(self.model)
                    
                    if latency != float('inf'):
                        all_latencies.append(latency)
                        logger.info(f"    -> Latency: {latency:.2f} ms")
                    else:
                        logger.warning(f"    -> Evaluation failed for device {device_ip}.")
                except Exception as e:
                    logger.error(f"    -> Error during evaluation on {device_ip}: {e}")
            
            if all_latencies:
                final_latency_ms = sum(all_latencies) / len(all_latencies)
                logger.info(f"Average real-device latency across {len(all_latencies)} devices: {final_latency_ms:.2f} ms")
            else:
                logger.warning("Real-device evaluation failed for all specified devices, latency will be null.")
        
        try:
            from app.models.model import Model, ModelVersion
            
            # 1. Find or Create Parent Model
            parent_model = Model.query.filter_by(name=self.task.model_name).first()
            if not parent_model:
                logger.warning(f"Parent model {self.task.model_name} not found. Creating new one.")
                parent_model = Model(
                    name=self.task.model_name,
                    type='DNN',
                    task_type='Image Classification' # Default
                )
                db.session.add(parent_model)
                db.session.commit()
            
            # 2. Prepare Metadata
            final_path = os.path.join(self.output_dir, 'compressed_model.pth')
            
            # Get metrics
            flops, params = 0.0, 0.0
            try:
                flops, params = self.pruner.get_flops_and_params(self.model)
            except:
                pass
            
            # Measure Final Accuracy
            acc_str = "N/A"
            if hasattr(self, 'evaluators') and 'accuracy' in self.evaluators:
                logger.info("Evaluating final model accuracy for registration...")
                try:
                    acc = self.evaluators['accuracy'].evaluate(self.model)
                    acc_str = f"Top-1 {acc*100:.2f}%"
                    logger.info(f"Final Accuracy: {acc_str}")
                except Exception as e:
                    logger.error(f"Failed to evaluate final accuracy: {e}")

            # Create Version Name (e.g. "compressed-v1" or timestamp)
            version_name = f"compressed-{int(time.time())}"
            
            # 3. Create ModelVersion
            new_version = ModelVersion(
                model_id=parent_model.id,
                device_type=self.task.device_type or 'CPU',
                name=version_name,
                type='DNN',
                file_path=final_path,
                dataset=self.model_version.dataset if self.model_version else 'cifar10',
                accuracy=acc_str,
                flops=flops,
                avg_latency_ms=final_latency_ms,
                compressed=True,
                source_task_id=self.task_id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(new_version)
            db.session.commit()
            logger.info(f"Registered compressed model version: {version_name} with Latency: {final_latency_ms} ms")
            
        except Exception as e:
            logger.error(f"Failed to register model: {e}")
            db.session.rollback()

    def _run_grid_search(self, evaluators):
        logger.info("Running Iterative Grid Search Strategy...")
        
        iterations = int(self.params.get('iterations', 10))
        epochs = int(self.params.get('train_epochs', 5))
        
        # ... (Grid generation logic) ...
        grid_rates_str = self.params.get('prune_rate_grid', '')
        if grid_rates_str:
            initial_grid_rates = [float(x) for x in grid_rates_str.split(',') if x.strip()]
        else:
            # Generate from min/max/step
            try:
                g_min = float(self.params.get('grid_min', 0.1))
                g_max = float(self.params.get('grid_max', 0.5))
                g_step = float(self.params.get('grid_step', 0.1))
                
                initial_grid_rates = []
                curr = g_min
                while curr <= g_max + 1e-9:
                    initial_grid_rates.append(round(curr, 2))
                    curr += g_step
            except Exception as e:
                logger.warning(f"Failed to generate grid from params: {e}. Using default.")
                initial_grid_rates = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        # Measure baseline accuracy if needed
        base_acc = None
        if 'accuracy_constraint' in self.params and 'accuracy' in evaluators:
             logger.info("Measuring baseline accuracy...")
             base_acc = evaluators['accuracy'].evaluate(self.model)
             logger.info(f"Baseline Accuracy: {base_acc}")
        
        for step in range(iterations):
            self._check_abort()
            logger.info(f"=== Grid Search Step {step+1}/{iterations} ===")
            
            # 1. Search
            logger.info("Searching for optimal layer-wise pruning rates using Grid Search...")
            # If user wants simple grid search, we should iterate over initial_grid_rates
            # and evaluate each one (applying same rate to all layers), then pick best.
            # This avoids "Generations" concept.
            
            import numpy as np
            best_rate = None
            max_score = -float('inf')
            best_details = {}
            
            # Use 'generations' param as a dummy if we are doing pure grid, 
            # or map 'grid rates' to generations?
            # User requirement: "Enumerate every pruning scheme".
            # Schemes: Uniform pruning with rate R from grid.
            
            for i, rate_val in enumerate(initial_grid_rates):
                self._check_abort()
                # Construct individual: all layers = rate_val
                # Or if we want to be fancy, we can support mixed rates but that's huge space.
                # Assuming Uniform Grid Search for now as it's standard.
                individual = np.full(len(self.current_layer_sizes), rate_val)
                
                # Evaluate (reuse EvolutionarySearch logic or manual)
                # Let's do manual evaluation to be clear
                # 1. Prune (temp)
                pruned_model = self.pruner.prune_by_rates(individual)
                
                # 2. Evaluate
                # Latency
                latency_score = 1.0
                if 'latency' in evaluators:
                     latency_score = evaluators['latency'].evaluate(pruned_model, individual)
                
                # Accuracy (Fast proxy?)
                acc_score = 1.0
                if 'accuracy' in evaluators:
                    acc_score = evaluators['accuracy'].evaluate(pruned_model)
                
                # Score
                # Minimize Latency, Maximize Acc using penalty formula
                # Obj = Normalized Latency
                # Penalty Formula: if Acc(M') >= alpha * Acc(M), Cost = Obj
                # else, Cost = Obj + (1 - Acc(M')) / (1 - alpha)
                # alpha is retention rate.
                
                obj = latency_score
                cost = obj
                
                if self.params.get('accuracy_constraint'):
                     limit = float(self.params.get('accuracy_constraint'))
                     if limit > 1.0: limit /= 100.0
                     
                     # Acc(M)
                     base = base_acc if base_acc else 0.8
                     
                     # alpha = (Base - Limit) / Base
                     # e.g. (0.93 - 0.02) / 0.93 = 0.91 / 0.93 = 0.978
                     if base > 1e-6:
                        alpha = (base - limit) / base
                     else:
                        alpha = 0.9 # Fallback
                     
                     # Check condition: Acc(M') >= alpha * Acc(M)
                     # equivalent to Acc(M') >= Base - Limit
                     threshold = alpha * base
                     
                     if acc_score < threshold:
                         # Penalty = (1 - Acc(M')) / (1 - alpha)
                         # 1 - alpha = 1 - (1 - Limit/Base) = Limit/Base
                         denominator = 1.0 - alpha
                         if denominator < 1e-6: denominator = 1e-6
                         
                         penalty = (1.0 - acc_score) / denominator
                         cost += penalty
                         logger.info(f"Rate {rate_val}: Constraint violated ({acc_score:.4f} < {threshold:.4f}). Penalty added: {penalty:.4f}")

                score = -cost
                
                # Get FLOPs
                flops, params = self.pruner.get_flops_and_params(pruned_model)
                
                # Convert normalized latency to absolute ms for logging
                abs_latency = latency_score
                if 'latency' in evaluators and hasattr(evaluators['latency'], 'base_latency'):
                     abs_latency = latency_score * evaluators['latency'].base_latency

                details = {
                    'latency': latency_score, # Keep internal normalized score for logic if needed
                    'abs_latency': abs_latency,
                    'flops': flops,
                    'accuracy': acc_score,
                    'rate': rate_val
                }
                
                # Log as if it was a generation (so chart works)
                self._log_metric('search', i+1, {'iteration': step+1, 'best_flops': flops, 'best_latency': abs_latency, 'best_accuracy': acc_score, 'score': score})
                
                logger.info(f"Grid Rate {rate_val}: Lat={latency_score:.2f} (Abs: {abs_latency:.2f}ms), Acc={acc_score:.2f}, Score={score:.4f}")
                
                if score > max_score:
                    max_score = score
                    best_rate = individual
                    best_details = details

            logger.info(f"Best Prune Rate for Step {step+1}: {best_details.get('rate')}")
            
            # 2. Apply Pruning
            logger.info("Pruning model...")
            self.model = self.pruner.prune_by_rates(best_rate)
            
            # Measure current performance
            flops, params = self.pruner.get_flops_and_params(self.model) # Pass NEW model to calculate FLOPs
            # Use evaluator for latency
            lat = 0
            if 'latency' in evaluators:
                 lat = evaluators['latency'].evaluate(self.model, best_rate)

            # Update pruner
            # Ensure example_input is 4D and on correct device
            example_input = torch.randn(1, *self.input_size).to(self.device)
            # Re-init pruner WITHOUT passing fixed layer_sizes, so it reads from the NEW pruned model
            self.pruner = ModelPruner(self.model, example_input)

            # 3. Finetune
            logger.info("Fine-tuning pruned model...")
            final_acc = self._finetune(epochs=epochs, iteration=step+1)
            
            # Log Iteration Metric (After finetune to get final accuracy)
            # Recalculate latency for logging (absolute ms)
            if 'latency' in evaluators and hasattr(evaluators['latency'], 'base_layer_sizes'):
                 # We need global rate for prediction
                 from app.core.compression.pruner import get_model_layer_sizes
                 curr_sizes = get_model_layer_sizes(self.model)
                 base_sizes = evaluators['latency'].base_layer_sizes
                 if len(curr_sizes) == len(base_sizes):
                     g_rate = 1.0 - (np.array(curr_sizes) / base_sizes)
                     lat = evaluators['latency'].predict_latency(g_rate)
            
            self._log_metric('pruning_iter', step+1, {
                'flops': flops, 
                'latency': lat,
                'prune_rate': float(sum(best_rate)/len(best_rate)),
                'accuracy': final_acc
            })
            
            # 4. Save
            self._save_result(suffix=f"_step{step+1}")
            
        self._save_result()

    def _run_hdap(self, evaluators):
        logger.info("Running HDAP Strategy...")
        iterations = int(self.params.get('iterations', 5))
        epochs = int(self.params.get('train_epochs', 5))
        
        for i in range(iterations):
            self._check_abort()
            logger.info(f"HDAP Iteration {i+1}/{iterations}")
            
            # Search
            def search_log_callback(gen, data):
                # Denormalize latency if present
                if 'best_latency' in data and 'latency' in evaluators and hasattr(evaluators['latency'], 'base_latency'):
                    data['best_latency'] = data['best_latency'] * evaluators['latency'].base_latency
                
                self._log_metric('search', gen, {'iteration': i+1, **data})

            searcher = EvolutionarySearch(
                evaluator=evaluators,
                pruner=self.pruner,
                population_size=int(self.params.get('pop_size', 10)),
                num_generations=int(self.params.get('generations', 5)),
                log_callback=search_log_callback,
                abort_callback=self._check_abort
            )
            
            best_rate = searcher.search()
            
            # Prune
            self.model = self.pruner.prune_by_rates(best_rate)
            
            # Log Iteration Metric
            # (Simplified, assume fake FLOPs for now if pruner method missing)
            self._log_metric('pruning_iter', i+1, {
                'flops': 0, 
                'latency': 0,
                'prune_rate': float(sum(best_rate)/len(best_rate))
            })
            
            # Update pruner
            # Ensure example_input is 4D
            example_input = torch.randn(1, *self.input_size).to(self.device)
            # Re-init pruner WITHOUT passing fixed layer_sizes, so it reads from the NEW pruned model
            self.pruner = ModelPruner(self.model, example_input)
            
            # Finetune
            self._finetune(epochs=epochs, iteration=i+1)
            
        self._save_result()

    def _check_abort(self):
        # Refresh task from DB to check status
        db.session.expire(self.task)
        if self.task.status == 'aborted':
            raise InterruptedError("Task aborted by user")

    def _finetune(self, epochs=1, iteration=1):
        logger.info(f"Finetuning for {epochs} epochs...")
        
        lr = float(self.params.get('lr', 0.01))
        batch_size = int(self.params.get('batch_size', 64)) 
        
        device = self.device
        self.model.to(device)
        
        # 1. Prepare Optimizer
        if 'get_optimizer' in self.custom_components:
            logger.info("Using custom get_optimizer")
            func = self.custom_components['get_optimizer']
            # Inspect args
            sig = inspect.signature(func)
            args = {}
            if 'model' in sig.parameters: args['model'] = self.model
            if 'lr' in sig.parameters: args['lr'] = lr
            optimizer = func(**args)
        else:
            optimizer = torch.optim.SGD(self.model.parameters(), lr=lr, momentum=0.9)

        # 2. Prepare Criterion
        if 'get_criterion' in self.custom_components:
            logger.info("Using custom get_criterion")
            criterion = self.custom_components['get_criterion']()
        else:
            criterion = torch.nn.CrossEntropyLoss()
        
        # 3. Train Loop
        train_func = self.custom_components.get('train_one_epoch')
        
        if train_func:
            logger.info("Using custom training function from model definition")
            for epoch in range(epochs):
                self._check_abort()
                # Dynamic Argument Injection
                sig = inspect.signature(train_func)
                args = {}
                
                # Available context
                context = {
                    'model': self.model,
                    'dataloader': self.train_loader,
                    'criterion': criterion,
                    'optimizer': optimizer,
                    'device': device,
                    'epoch': epoch,
                    'lr': lr
                }
                
                for param_name in sig.parameters:
                    if param_name in context:
                        args[param_name] = context[param_name]
                
                # Call
                try:
                    result = train_func(**args)
                    
                    # Handle return values (avg_loss, acc) or just loss
                    avg_loss, acc = 0.0, 0.0
                    if isinstance(result, tuple) and len(result) >= 2:
                        avg_loss, acc = result[0], result[1]
                    elif isinstance(result, (float, int)):
                        avg_loss = result
                    
                    logger.info(f"[Epoch {epoch+1}] Loss: {avg_loss:.4f}, Acc: {acc:.2f}%")
                    
                    self._log_metric('finetune', epoch+1, {
                        'iteration': iteration,
                        'loss': avg_loss,
                        'accuracy': acc
                    })
                except Exception as e:
                    logger.error(f"Error during custom train_one_epoch: {e}")
                    break
            
            return acc
        else:
            logger.info("Using default training loop")
            self.model.train()
            last_acc = 0.0
            for epoch in range(epochs):
                self._check_abort()
                running_loss = 0.0
                total_batches = len(self.train_loader)
                
                for i, (inputs, labels) in enumerate(self.train_loader):
                    inputs, labels = inputs.to(device), labels.to(device)
                    
                    optimizer.zero_grad()
                    outputs = self.model(inputs)
                    loss = criterion(outputs, labels)
                    
                    if torch.isnan(loss):
                        logger.error(f"[Epoch {epoch+1}] Batch {i}: Loss is NaN! Skipping batch.")
                        optimizer.zero_grad()
                        continue
                        
                    loss.backward()
                    
                    # Gradient Clipping
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), 10.0)
                    
                    optimizer.step()
                    
                    running_loss += loss.item()
                    if i % 10 == 0:
                         logger.info(f"[Epoch {epoch+1}] Batch {i}: Loss {loss.item():.4f}")
                
                avg_loss = running_loss / total_batches
                
                # Evaluate
                acc = 0.0
                if hasattr(self, 'evaluators') and 'accuracy' in self.evaluators:
                     acc = self.evaluators['accuracy'].evaluate(self.model)
                
                # Log simplified metric
                self._log_metric('finetune', epoch+1, {
                    'iteration': iteration,
                    'loss': avg_loss,
                    'accuracy': acc 
                })
                last_acc = acc
            return last_acc

    def _save_result(self, suffix=""):
        save_path = os.path.join(self.output_dir, f'compressed_model{suffix}.pth')
        torch.save(self.model.state_dict(), save_path)
        logger.info(f"Model saved to {save_path}")
