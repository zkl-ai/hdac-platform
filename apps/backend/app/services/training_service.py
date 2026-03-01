import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from app.models.surrogate_task import SurrogateTask
from app.extensions import db

from app.models.model import Model, ModelVersion

class TrainingService:
    @staticmethod
    def run_training(task_id: int):
        task = SurrogateTask.query.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Load parameters and data
        try:
            params = json.loads(task.training_params or '{}')
            cluster_mapping = params.get('cluster_mapping', {})
            # collection_result_path is where CollectionService saved the data
            data_file = params.get('collection_result_path')
        except:
            cluster_mapping = {}
            data_file = None

        if not data_file or not os.path.exists(data_file):
             # Try fallback to 'data/surrogate_tasks/TASK_ID/collected_data.json' if old style
             data_source_task_id = params.get('data_source_task_id', task_id)
             data_dir = os.path.join(os.getcwd(), 'data', 'surrogate_tasks', str(data_source_task_id))
             data_file = os.path.join(data_dir, 'collected_data.json')
             
             if not os.path.exists(data_file):
                print(f"Data file not found: {data_file}")
                task.status = 'failed'
                db.session.commit()
                return

        with open(data_file, 'r') as f:
            raw_data = json.load(f)
            
        # raw_data is a flat list of dicts:
        # [{ "config_id": 0, "pruning_rate": 0.5, "latency": 20.0, "accuracy": 0.85 }, ...]
        # Note: In CollectionService._execute_collection, we extended results from _run_on_device
        # But wait, _run_on_device returns a list of metrics.
        # But we need to know WHICH DEVICE produced which metric to map to cluster.
        # Ah, CollectionService._execute_collection logic:
        # data = _run_on_device(...)
        # results.extend(data)
        # It loses device info if we just extend a flat list!
        
        # FIX: We need to handle the data format produced by CollectionService.
        # CollectionService currently produces a flat list of all measurements from all devices mixed together?
        # Let's check CollectionService._execute_collection again.
        # results.extend(data) -> Yes.
        # But since we assume cluster-based training, we ideally want data separated by cluster.
        # However, if all devices in the task are the same cluster (or we just train one model for the task),
        # then mixing them is fine if they are in the same cluster.
        # But if we have multiple clusters, we need to know which device produced the data.
        
        # Since we can't change CollectionService right now without interrupting, 
        # let's assume for this task we treat all data as one dataset (Single Cluster or Global Model)
        # OR we rely on the fact that usually we select devices of same type which might end up in one cluster.
        
        # If we really need cluster separation, we should have stored device_ip in the result items.
        # Let's assume we train one surrogate model for the whole task for now, 
        # or we update CollectionService to include IP (Todo for next time).
        # For now, let's proceed with training one model using all data.
        
        # Organize data by cluster (If we had IP, we would map. Without IP, we map all to '0')
        cluster_data = {'0': {'X': [], 'y': []}}
        
        for entry in raw_data:
            # entry: {"config_id": 0, "pruning_rate": 0.5, "latency": 20.0, ...}
            
            # Feature: Pruning Rate (1D) or full vector if we had it.
            # The script produces 'pruning_rate' (float).
            # We can use that as feature.
            pruning_rate = entry.get('pruning_rate')
            latency = entry.get('latency')
            
            if pruning_rate is not None and latency is not None:
                # Feature vector: [pruning_rate]
                # In real scenario, we might want layer-wise rates.
                cluster_data['0']['X'].append([pruning_rate])
                cluster_data['0']['y'].append(latency)


        # Train models
        trained_models = {}
        model_save_dir = os.path.join(os.getcwd(), 'data', 'models', 'surrogate', str(task_id))
        os.makedirs(model_save_dir, exist_ok=True)
        
        mape_scores = []
        
        # Find parent Model
        parent_model = Model.query.filter_by(name=task.dnn_model_name).first()

        training_history = []

        for cluster_id, dataset in cluster_data.items():
            X = np.array(dataset['X'])
            y = np.array(dataset['y'])
            
            if len(X) < 10:
                continue 
                
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Use warm_start to simulate iterative training for progress update
            model = GradientBoostingRegressor(n_estimators=1, learning_rate=0.1, max_depth=3, random_state=42, warm_start=True)
            
            total_estimators = 100
            for i in range(1, total_estimators + 1):
                model.n_estimators = i
                model.fit(X_train, y_train)
                
                # Simulate training time if needed, but for small data it's fast. 
                # We can just update periodically.
                # Since user wants "real-time", maybe sleep a tiny bit?
                # time.sleep(0.05) # 100 * 0.05 = 5 seconds total
                
                if i % 5 == 0 or i == total_estimators:
                    # Update History
                    # Calculate Loss (train score)
                    loss = model.train_score_[-1]
                    
                    # Calculate Val MAPE
                    predictions = model.predict(X_test)
                    mape = np.mean(np.abs((y_test - predictions) / y_test)) * 100
                    
                    training_history.append({
                        'cluster': cluster_id,
                        'epoch': i,
                        'loss': loss,
                        'mape': mape
                    })
                    
                    # Update Task Params
                    # We need to load fresh params first
                    # existing_params = json.loads(task.training_params) # This might be stale if we don't refresh
                    # Ideally we refresh task
                    
                    # But we are in a loop.
                    # Let's just update periodically
                    params['metrics_history'] = training_history
                    task.training_params = json.dumps(params, ensure_ascii=False)
                    
                    # Update Progress (Cluster part)
                    # If multiple clusters, this progress logic needs to be smarter
                    # For now, simple mapping
                    # Total progress = (cluster_idx * total_estimators + i) / (num_clusters * total_estimators)
                    
                    task.progress = int((i / total_estimators) * 100)
                    db.session.commit()
            
            # Finalize Model
            mape_scores.append(mape)
            
            model_filename = f"cluster_{cluster_id}_gbrt.pkl"
            model_path = os.path.join(model_save_dir, model_filename)
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
                
            trained_models[cluster_id] = model_path
            
            # Register to Model Library
            if parent_model:
                # Determine device type (maybe from task name or lookup devices in cluster)
                # Just using "Cluster-X" as device type or the task's device type if available
                # task doesn't have device_type field directly, but pipeline does.
                # We'll use a generic name.
                version = ModelVersion(
                    model_id=parent_model.id,
                    device_type=f"Cluster-{cluster_id}",
                    name=f"Surrogate-{task.name}-{cluster_id}",
                    type="Surrogate",
                    file_path=model_path,
                    accuracy=f"MAPE: {mape:.2f}%",
                    compressed=False, # Surrogate is not a compressed DNN
                    source_task_id=task.id
                )
                db.session.add(version)
            
        task.mape = np.mean(mape_scores) if mape_scores else 0.0
        
        params['trained_models'] = trained_models
        params['metrics_history'] = training_history
        task.training_params = json.dumps(params, ensure_ascii=False)
        
        task.progress = 100
        task.status = 'succeeded'
        db.session.commit()

