from flask import Blueprint, request
from app.extensions import db
from sqlalchemy import text
from app.models.model import Model, ModelVersion
from app.models.dataset import Dataset
from app.utils.response import success, fail
import os
import subprocess
import paramiko
from werkzeug.utils import secure_filename
from app.models.device import Device
from app.routes.device import _read_registry
import json
from datetime import datetime
from app.models.surrogate_pipeline import SurrogatePipeline
from app.models.surrogate_task import SurrogateTask

model_bp = Blueprint('model_library', __name__, url_prefix='/api')

MODELS_DIR = "/data/workspace/hdap-platform/database/models"

@model_bp.get('/models/proxies')
def list_proxies():
    try:
        model_name = (request.args.get('modelName') or '').strip()
        device_type = (request.args.get('deviceType') or '').strip()
        
        if not model_name or not device_type:
             return success(data={'items': []})

        # Find the parent model first
        parent_model = Model.query.filter_by(name=model_name).first()
        if not parent_model:
            return success(data={'items': []})

        # Query ModelVersion instead of SurrogatePipeline
        # We look for versions of type 'Surrogate' linked to this model
        q = ModelVersion.query.filter_by(
            model_id=parent_model.id,
            type='Surrogate'
        ).order_by(ModelVersion.created_at.desc())
        
        items = []
        for v in q.all():
            # Check if this surrogate is for the target device
            # Strategy 1: Check v.device_type (if it was saved correctly)
            if v.device_type == device_type:
                items.append({
                    'label': v.name,
                    'value': v.name, # Use name as value? Or ID? StartCompressModal uses value for proxyModel field.
                    # Backend pipeline expects proxy_model parameter.
                    # If we pass name, we need to handle it. 
                    # app/core/compression/evaluator.py SurrogateLatencyEvaluator uses `model_name`.
                    # But wait, SurrogateLatencyEvaluator logic:
                    # `model_dir = os.path.join(surrogate_dir, f'nano_{model_name}_latency_model')`
                    # It seems it constructs path based on model_name.
                    # If we use `proxy_model` param, how is it used?
                    # In `pipeline.py`: `if use_proxy: evaluators['latency'] = SurrogateLatencyEvaluator(self.task.model_name, ...)`
                    # It ignores `proxy_model` param value! It just uses `task.model_name`.
                    # This implies `SurrogateLatencyEvaluator` assumes a standard naming or location.
                    
                    # However, if we support multiple proxies (clusters), we must pass the specific one.
                    # The user wants to select a specific proxy.
                    # We should probably update `pipeline.py` to use the selected proxy.
                    # For now, let's return the name as value, as that's unique enough.
                    'key': str(v.id),
                    'status': 'succeeded', # ModelVersions are results, so they are succeeded
                    'time': v.time
                })
            # Strategy 2: Check naming convention if device_type is Cluster-X
            elif v.name and f"-{device_type}-" in v.name:
                 items.append({
                    'label': v.name,
                    'value': v.name,
                    'key': str(v.id),
                    'status': 'succeeded',
                    'time': v.time
                })
            
        return success(data={'items': items})
    except Exception as e:
        return fail(message=str(e))


@model_bp.get('/models/tree')
def models_tree():
    try:
        mtype = request.args.get('type')  # DNN / Surrogate / None
        q = Model.query
        if mtype:
            q = q.filter_by(type=mtype)
        models = q.order_by(Model.name.asc()).all()
        model_ids = [m.id for m in models]
        
        versions = []
        if model_ids:
            versions = ModelVersion.query.filter(ModelVersion.model_id.in_(model_ids)).all()
            
        v_by_model = {}
        for v in versions:
            v_by_model.setdefault(v.model_id, {}).setdefault(v.device_type, []).append(v)

        # Get all distinct device types from Device library
        all_device_types = [r[0] for r in db.session.query(Device.type).distinct().filter(Device.type != None, Device.type != '').all()]
        
        tree = []
        for m in models:
            dev_groups = v_by_model.get(m.id, {})
            children = []
            
            # Merge device types from library and existing versions
            used_types = set(dev_groups.keys())
            combined_types = sorted(list(set(all_device_types) | used_types))
            
            for dt in combined_types:
                v_list = dev_groups.get(dt, [])
                v_nodes = []
                for v in v_list:
                    # Special handling for Surrogate Models:
                    # If model is Surrogate, the version represents a specific cluster model
                    # But the requirement is:
                    # Level 1: "ResNet-Tiny-56" (DNN Model) -> Done
                    # Level 2: "Jetson Xavier NX" (Device Type) -> Done
                    # Level 3: "Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0" (Surrogate Task Name) -> This is v.name
                    # Level 4: "Cluster-0" -> This should be under Level 3
                    
                    # However, currently the tree structure is only 3 levels deep in frontend.
                    # Frontend renders Level 1 (Model), Level 2 (Device), Level 3 (Version).
                    # If we want to show Cluster-0 under Surrogate-Task-Name, we need Level 4.
                    # Or we can treat Surrogate-Task-Name as a "Device Type" group? No, that's weird.
                    
                    # Let's check the current data structure for Surrogate models.
                    # When training finishes, we save:
                    # ModelVersion(name="Surrogate-{task.name}-{cluster_id}", device_type="Cluster-{cluster_id}")
                    # Wait, in training_service.py:
                    # version = ModelVersion(
                    #     model_id=parent_model.id,
                    #     device_type=f"Cluster-{cluster_id}",  <-- This is the issue!
                    #     name=f"Surrogate-{task.name}-{cluster_id}",
                    #     ...
                    # )
                    
                    # The user wants:
                    # L1: ResNet-Tiny-56
                    #   L2: Jetson Xavier NX  (Target Device Type)
                    #     L3: Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0
                    #       L4: Cluster-0
                    
                    # But currently we save device_type as "Cluster-0".
                    # So it shows up as L1: ResNet -> L2: Cluster-0 -> L3: Surrogate...
                    
                    # WE NEED TO FIX THE DATA SAVING LOGIC FIRST (for new tasks), 
                    # OR HACK THE TREE GENERATION (for existing data).
                    # Since we can't easily change old data without migration, let's adjust the tree generation.
                    
                    # If the version name starts with "Surrogate-", we try to parse the real target device type.
                    # Name format: Surrogate-{task.name}-{cluster_id}
                    # Task name format: 训练-{model}-{device_type} (from pipeline creation)
                    # So version name: Surrogate-训练-{model}-{device_type}-{cluster_id}
                    
                    # Example: Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0
                    # Real Device Type: Jetson Xavier NX
                    # Cluster ID: 0 (or derived from end of string)
                    
                    # So, if we detect this pattern, we should move this version node UNDER "Jetson Xavier NX" group,
                    # AND maybe create a sub-structure or just rename it?
                    
                    # User wants L3 to be the Task Name, and L4 to be Cluster.
                    # Current frontend supports L3.
                    # Maybe we can make:
                    # L3: Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0 (The "Version" Name)
                    # And inside L3, we show "Cluster-0" as some attribute?
                    # OR, we change the structure to 4 levels.
                    
                    # Let's stick to 3 levels for now to avoid breaking frontend too much, 
                    # unless we really need 4 levels.
                    # "Cluster-0应该放在...条目下" implies hierarchy.
                    
                    # If we change device_type in DB to "Jetson Xavier NX", 
                    # then it will appear under L2 "Jetson Xavier NX".
                    # Then L3 will be "Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0".
                    # Then where does "Cluster-0" go?
                    # It can be part of the L3 name or a tag.
                    
                    # But wait, the user says:
                    # "Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0" should be under "Jetson Xavier NX" -> This confirms we need to fix device_type.
                    # "Cluster-0 should be under Surrogate...0" -> This implies L4.
                    
                    # Let's try to parse and regroup in the tree generation.
                    
                    node = {
                        'id': v.id,
                        'name': v.name,
                        'type': v.type,
                        'dataset': v.dataset,
                        'datasetAccuracy': v.accuracy,
                        'flops': v.flops,
                        'avgLatencyMs': v.avg_latency_ms,
                        'compressed': v.compressed,
                        'time': v.time,
                        'deviceType': dt,
                        'modelName': m.name,
                        'level': 3,
                        'sourceTaskId': v.source_task_id
                    }
                    
                    # Inject Cluster Count for Surrogate Models
                    if v.type == 'Surrogate' or v.name.startswith('Surrogate-'):
                        try:
                            node['clusterCount'] = 0
                            if v.source_task_id:
                                t = SurrogateTask.query.get(v.source_task_id)
                                if t and t.training_params:
                                    tp = json.loads(t.training_params)
                                    tm = tp.get('trained_models', {})
                                    if tm:
                                        node['clusterCount'] = len(tm)
                                    else:
                                        hist = tp.get('metrics_history', [])
                                        clusters = set([x.get('cluster') for x in hist if 'cluster' in x])
                                        node['clusterCount'] = len(clusters)
                        except Exception as e:
                            print(f"Error getting cluster count: {e}")
                            node['clusterCount'] = 0
                    
                    # Hack for Surrogate Models with wrong device_type "Cluster-X"
                    if v.type == 'Surrogate' and v.device_type.startswith('Cluster-'):
                        # Try to extract real device type from name
                        # Name: Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0
                        # We know model name: ResNet-Tiny-56
                        # Prefix: Surrogate-训练-{model_name}-
                        prefix = f"Surrogate-训练-{m.name}-"
                        if v.name.startswith(prefix):
                            rest = v.name[len(prefix):]
                            # rest: Jetson Xavier NX-0
                            # We assume the last part is cluster ID separated by hyphen? 
                            # But device type might contain hyphens (e.g. "Jetson-Nano").
                            # However, cluster ID is usually single digit or number at end.
                            # Let's assume the suffix "-{cluster_id}"
                            
                            import re
                            match = re.search(r'-(?P<cluster>\d+)$', rest)
                            if match:
                                cluster_id = match.group('cluster')
                                real_device_type = rest[:match.start()]
                                
                                # We want to put this node under `real_device_type` group instead of `dt` (Cluster-X)
                                # But we are iterating `dt`.
                                # We should handle this by preprocessing or post-processing.
                                
                                # Easier way: Just modify the node here, but we are inside the wrong `dt` loop.
                                # Wait, `v_by_model` groups by `device_type`.
                                # So these versions are currently in `dev_groups['Cluster-0']`.
                                # We need to move them to `dev_groups['Jetson Xavier NX']`.
                                pass

                    v_nodes.append(node)
                
                children.append({
                    'id': f"d-{m.id}-{dt}",
                    'name': dt,
                    'deviceType': dt,
                    'children': v_nodes,
                    'modelName': m.name,
                    'level': 2
                })
            
            # --- Regrouping Logic Start ---
            # We iterate through children (Device Groups) and move Surrogate nodes from "Cluster-X" groups to real Device groups.
            
            # 1. Find all "Cluster-X" groups
            cluster_groups = [g for g in children if g['deviceType'].startswith('Cluster-')]
            
            # 2. Process each Surrogate node in these groups
            for cg in cluster_groups:
                # We will remove nodes from here and add to target group
                # Or just remove the whole group if empty
                
                nodes_to_move = []
                for node in cg['children']:
                    if node['type'] == 'Surrogate' and node['name'].startswith(f"Surrogate-训练-{m.name}-"):
                        prefix = f"Surrogate-训练-{m.name}-"
                        rest = node['name'][len(prefix):]
                        import re
                        match = re.search(r'-(?P<cluster>\d+)$', rest)
                        if match:
                            cluster_id = match.group('cluster')
                            real_device_type = rest[:match.start()]
                            
                            # Construct L4 node structure
                            # The current node becomes L3 (Task Name) -> But wait, task name includes cluster?
                            # Task Name in DB: 训练-{model}-{device}
                            # Version Name: Surrogate-{task.name}-{cluster}
                            # So Version Name is unique per cluster.
                            
                            # User wants:
                            # L2: Jetson Xavier NX
                            #   L3: Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0  (This is the Version Name)
                            #     L4: Cluster-0
                            
                            # Actually, if the Version Name ALREADY contains the Cluster ID (ending in -0), 
                            # and user wants "Cluster-0" UNDER it, it means the Version Node should have children?
                            # But ModelVersion is a leaf.
                            
                            # Maybe user means:
                            # L3: Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX (The Task)
                            #   L4: Cluster-0 (The Version)
                            
                            # But currently we don't have a "Task" object in the tree, only ModelVersion.
                            # We can synthesize an L3 group.
                            
                            task_base_name = f"Surrogate-训练-{m.name}-{real_device_type}"
                            
                            nodes_to_move.append({
                                'node': node,
                                'target_device': real_device_type,
                                'cluster_name': f"Cluster-{cluster_id}",
                                'task_group_name': node['name'] # User said "Surrogate...NX-0" should be the L3 item?
                                # Wait, user said:
                                # 代理模型构建任务名称“Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0”应该放在二级条目“Jetson Xavier NX”下
                                # Cluster-0应该放在“Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0”条目下
                                
                                # This means:
                                # L2: Jetson Xavier NX
                                #   L3: Surrogate-训练-ResNet-Tiny-56-Jetson Xavier NX-0
                                #     L4: Cluster-0
                                
                                # So L3 is the Version (which represents the task result for that cluster).
                                # And L4 is just a detail showing "Cluster-0".
                                # OR L3 is the "Task" and L4 is the "Version".
                                
                                # If L3 is "Surrogate...NX-0", that is exactly the `v.name`.
                                # So we just need to:
                                # 1. Move this node under "Jetson Xavier NX" group.
                                # 2. Add a child to this node named "Cluster-0".
                            })

                for item in nodes_to_move:
                    node = item['node']
                    target_device = item['target_device']
                    
                    # Find or create target device group
                    target_group = next((g for g in children if g['deviceType'] == target_device), None)
                    if not target_group:
                        target_group = {
                            'id': f"d-{m.id}-{target_device}",
                            'name': target_device,
                            'deviceType': target_device,
                            'children': [],
                            'modelName': m.name,
                            'level': 2
                        }
                        children.append(target_group)
                    
                    # Modify node to be L3
                    node['level'] = 3
                    # Add L4 child
                    node['children'] = [{
                        'id': f"{node['id']}-c",
                        'name': item['cluster_name'],
                        'level': 4,
                        'type': 'ClusterInfo' # Marker
                    }]
                    
                    # Add to target group
                    target_group['children'].append(node)
                    
                    # Remove from original group
                    cg['children'] = [n for n in cg['children'] if n['id'] != node['id']]

            # Filter out empty Cluster groups
            children = [g for g in children if not (g['deviceType'].startswith('Cluster-') and len(g['children']) == 0)]
            # --- Regrouping Logic End ---
            
            tree.append({
                'id': f"m-{m.id}",
                'name': m.name,
                'type': m.type,
                'children': children,
                'level': 1,
                'inputDim': m.input_dim,
                'outputDim': m.output_dim,
                'taskType': m.task_type,
                'modelFlops': m.model_flops,
                'createdBy': m.created_by or 'alice_admin'
            })
        
        return success({'items': tree})
    except Exception as e:
        return fail(message=f'查询失败: {e}', code=500, http_status=500)


@model_bp.post('/models/seed')
def models_seed():
    try:
        # Check if force reset is requested
        force = bool(request.json and request.json.get('force'))

        if force:
            # Clear existing data
            ModelVersion.query.delete()
            Model.query.delete()
            Dataset.query.delete()
            db.session.flush()
            
            try:
                db.session.execute(text("ALTER TABLE datasets AUTO_INCREMENT = 1"))
                db.session.execute(text("ALTER TABLE models AUTO_INCREMENT = 1"))
                db.session.execute(text("ALTER TABLE model_versions AUTO_INCREMENT = 1"))
            except Exception as e:
                print(f"Warning: Failed to reset auto_increment: {e}")

        # Ensure default dataset exists
        default_datasets = [
            {'name': 'CIFAR-10', 'path': '/data/workspace/datasets/cifar10', 'type': 'Image Classification', 'desc': 'CIFAR-10 Dataset'},
            {'name': 'MNIST', 'path': '/data/workspace/datasets/MNIST', 'type': 'Image Classification', 'desc': 'MNIST Handwritten Digits'},
            {'name': 'VOC', 'path': '/data/workspace/datasets/VOC', 'type': 'Object Detection', 'desc': 'PASCAL VOC Dataset'},
            {'name': 'ImageNet', 'path': '/data/workspace/datasets/imagenet', 'type': 'Image Classification', 'desc': 'ImageNet Large Scale Visual Recognition Challenge'},
        ]

        for ds_info in default_datasets:
            exist = Dataset.query.filter_by(name=ds_info['name']).first()
            if not exist:
                ds = Dataset(
                    name=ds_info['name'], 
                    path=ds_info['path'], 
                    type=ds_info['type'], 
                    description=ds_info['desc']
                )
                db.session.add(ds)
            elif exist.path != ds_info['path']: # Update path if mismatch
                exist.path = ds_info['path']

        # Create Models if not exist
        if Model.query.count() == 0:
            # Only create ResNet-Tiny-56 as requested, removing other mock models
            # 126 MFLOPs = 126,000,000
            reset_tiny = Model(name='ResNet-Tiny-56', type='DNN', task_type='Image Classification', input_dim='1x32x32x3', output_dim='10', model_flops=126000000)
            
            db.session.add(reset_tiny)
            db.session.flush()

            # Create Versions
            versions = [
                # ResNet-Tiny-56 (New)
                ModelVersion(
                    model_id=reset_tiny.id, 
                    device_type='Jetson Xavier NX', 
                    name='uncompressed', 
                    type='DNN', 
                    dataset='CIFAR-10', 
                    accuracy='Top-1 93.0%', 
                    flops=126000000, 
                    avg_latency_ms=4.5, 
                    compressed=False, 
                    file_path='/data/workspace/hdap-platform/database/models/ResNet-Tiny-56/uncompressed/model.pth',
                    time=datetime.now().strftime('%Y-%m-%d %H:%M')
                ),
            ]
            db.session.add_all(versions)
            
            # Ensure Device library has these types
            for dtype in ['Jetson Xavier NX']:
                if not Device.query.filter_by(type=dtype).first():
                    # Create a placeholder device if not exists
                    dummy_ip = f"192.168.1.{100 + len(dtype)}"
                    if not Device.query.filter_by(ip=dummy_ip).first():
                        d = Device(ip=dummy_ip, type=dtype, status='offline')
                        db.session.add(d)
        
        db.session.commit()
        return success(message='模型库种子数据已写入')
    except Exception as e:
        db.session.rollback()
        return fail(message=f'种子数据写入失败: {e}', code=500, http_status=500)


@model_bp.post('/models/perf')
def create_model_perf():
    try:
        payload = request.get_json(force=True) or {}
        model_name = (payload.get('modelName') or '').strip()
        model_type = (payload.get('modelType') or '').strip() or 'DNN'
        dataset_name = (payload.get('datasetName') or '').strip()
        dataset_accuracy = (payload.get('datasetAccuracy') or '').strip() or None
        device_type = (payload.get('deviceType') or '').strip()
        version_name = (payload.get('versionName') or '').strip() or 'uncompressed'
        
        flops = payload.get('flops')
        avg_latency_ms = payload.get('avgLatencyMs')
        compressed = bool(payload.get('compressed'))
        time_str = (payload.get('time') or '').strip() or None
        input_dim = (payload.get('inputDim') or '').strip()
        output_dim = (payload.get('outputDim') or '').strip()
        task_type = (payload.get('taskType') or '').strip()
        model_flops_req = payload.get('modelFlops')
        auto_flops = bool(payload.get('autoFlops'))
        measure_latency = bool(payload.get('measureLatency'))

        if not model_name or not device_type:
             return fail(message='缺少必要字段: modelName / deviceType', code=400, http_status=400)
             
        m = Model.query.filter_by(name=model_name).first()
        if not m:
            m = Model(name=model_name, type=model_type)
            db.session.add(m)
            db.session.flush()

        # Update Model Metadata
        if input_dim: m.input_dim = input_dim
        if output_dim: m.output_dim = output_dim
        if task_type: m.task_type = task_type
        if model_flops_req: m.model_flops = model_flops_req
        
        if (flops is None) and auto_flops:
            try:
                script_path = '/data/workspace/hdap-platform/infra/tools/calc_flops.py'
                if os.path.exists(script_path):
                    out = subprocess.check_output(['python3', script_path, '--model', model_name, '--input', input_dim], stderr=subprocess.STDOUT, timeout=15)
                    try:
                        flops = float(out.decode('utf-8').strip())
                    except Exception:
                        flops = None
            except Exception:
                flops = None
        
        # If auto-calc flops succeeded and model doesn't have it, update model
        if flops and not m.model_flops:
            m.model_flops = flops
        
        if (avg_latency_ms is None) and measure_latency:
            try:
                reg = _read_registry()
                ip = None
                for it in reg:
                    if it.get('type') == device_type and it.get('status') == 'online':
                        ip = it.get('ip')
                        break
                if ip:
                    dev = Device.query.filter_by(ip=ip).first()
                    if dev and dev.username and dev.password:
                        client = paramiko.SSHClient()
                        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        client.connect(ip, port=dev.port or 22, username=dev.username, password=dev.password, timeout=10)
                        cmd = f"python3 /opt/hdap/measure_latency.py --model '{model_name}' --input '{input_dim}'"
                        stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
                        out = stdout.read().decode('utf-8').strip()
                        client.close()
                        try:
                            avg_latency_ms = float(out)
                        except Exception:
                            avg_latency_ms = None
            except Exception:
                avg_latency_ms = None

        v = ModelVersion(
            model_id=m.id,
            device_type=device_type,
            name=version_name,
            type=model_type,
            dataset=dataset_name,
            accuracy=dataset_accuracy,
            flops=flops,
            avg_latency_ms=avg_latency_ms,
            compressed=compressed,
            time=time_str or datetime.now().strftime('%Y-%m-%d %H:%M')
        )
        db.session.add(v)
        
        db.session.commit()
        return success(message='已创建版本条目', data={'modelId': m.id, 'versionId': v.id})
    except Exception as e:
        db.session.rollback()
        return fail(message=f'创建失败: {e}', code=500, http_status=500)


@model_bp.delete('/models/perf/<int:perf_id>')
def delete_model_perf(perf_id: int):
    try:
        v = ModelVersion.query.get(perf_id)
        if not v:
            return fail(message='未找到版本条目', code=404, http_status=404)
        db.session.delete(v)
        db.session.commit()
        return success(message='已删除版本条目')
    except Exception as e:
        db.session.rollback()
        return fail(message=f'删除失败: {e}', code=500, http_status=500)


@model_bp.delete('/models/by_name/<string:model_name>')
def delete_model_by_name(model_name: str):
    try:
        m = Model.query.filter_by(name=model_name).first()
        if not m:
            return fail(message='未找到模型', code=404, http_status=404)
        ModelVersion.query.filter_by(model_id=m.id).delete()
        db.session.delete(m)
        db.session.commit()
        return success(message='已删除模型及其所有版本')
    except Exception as e:
        db.session.rollback()
        return fail(message=f'删除失败: {e}', code=500, http_status=500)


@model_bp.post('/models/upload')
def upload_model():
    try:
        if 'file' not in request.files:
            return fail(message='No file part', code=400, http_status=400)
        file = request.files['file']
        
        # Optional definition and profiler files
        definition_file = request.files.get('definitionFile')
        profiler_file = request.files.get('profilerFile')
        
        if file.filename == '':
            return fail(message='No selected file', code=400, http_status=400)
        
        name = (request.form.get('name') or '').strip()
        version_name = (request.form.get('version') or '').strip()
        dataset_name = (request.form.get('dataset') or '').strip()
        device_type = (request.form.get('deviceType') or '').strip()
        
        if not name or not version_name or not dataset_name or not device_type:
             return fail(message='Missing required fields', code=400, http_status=400)
             
        filename = secure_filename(file.filename)
        # Use new storage path
        save_dir = f"{MODELS_DIR}/{name}/{version_name}"
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, filename)
        file.save(file_path)
        
        definition_path = None
        if definition_file and definition_file.filename:
            d_filename = secure_filename(definition_file.filename)
            definition_path = os.path.join(save_dir, d_filename)
            definition_file.save(definition_path)
            
        profiler_path = None
        if profiler_file and profiler_file.filename:
            p_filename = secure_filename(profiler_file.filename)
            profiler_path = os.path.join(save_dir, p_filename)
            profiler_file.save(profiler_path)
        
        # Create Model if not exists
        m = Model.query.filter_by(name=name).first()
        if not m:
            m = Model(name=name, type='DNN')
            db.session.add(m)
            db.session.flush()
            
        # Update Model Metadata from form
        input_dim = request.form.get('inputDim', '')
        output_dim = request.form.get('outputDim', '')
        task_type = request.form.get('taskType', 'Image Classification')
        
        if input_dim: m.input_dim = input_dim
        if output_dim: m.output_dim = output_dim
        if task_type: m.task_type = task_type
            
        # Create Version
        v = ModelVersion(
            model_id=m.id,
            device_type=device_type,
            name=version_name,
            type='DNN',
            dataset=dataset_name,
            file_path=file_path,
            definition_path=definition_path,
            profiler_path=profiler_path,
            compressed=False, 
            accuracy='Untrained',
            time=datetime.now().strftime('%Y-%m-%d %H:%M')
        )
        db.session.add(v)
        
        db.session.commit()
        return success(message='Model uploaded successfully', data={'modelId': m.id, 'versionId': v.id})
    except Exception as e:
        db.session.rollback()
        return fail(message=f'Upload failed: {e}', code=500, http_status=500)
