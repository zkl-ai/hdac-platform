from flask import Blueprint, request
import random
import json
import os
import logging

from app.extensions import db
from app.models.compress_task import CompressTask, CompressStage
from app.models.device import Device
from app.models.model import Model, ModelVersion
from app.utils.response import success, fail
from app.services.compress_runner import CompressTaskRunner

logger = logging.getLogger(__name__)

compress_bp = Blueprint('compress_task', __name__, url_prefix='/api')


@compress_bp.get('/compress/tasks')
def list_compress_tasks():
    q = CompressTask.query
    kw = (request.args.get('keyword') or '').strip()
    model_name = (request.args.get('modelName') or '').strip()
    device_type = (request.args.get('deviceType') or '').strip()
    status = (request.args.get('status') or '').strip()

    if kw:
        like = f"%{kw}%"
        q = q.filter(CompressTask.name.ilike(like))
    if model_name:
        q = q.filter(CompressTask.model_name == model_name)
    if device_type:
        q = q.filter(CompressTask.device_type == device_type)
    if status:
        q = q.filter(CompressTask.status == status)

    tasks = q.order_by(CompressTask.created_at.desc()).all()
    task_ids = [t.id for t in tasks]
    stages = (
        CompressStage.query.filter(CompressStage.task_id.in_(task_ids)).all()
        if task_ids
        else []
    )
    by_tid = {}
    for s in stages:
        by_tid.setdefault(s.task_id, []).append(s)

    items = []
    for t in tasks:
        d = t.to_dict()
        d['stages'] = [s.to_dict() for s in by_tid.get(t.id, [])]
        items.append(d)

    return success(data={'items': items})


@compress_bp.get('/compress/tasks/<int:task_id>')
def get_compress_task_detail(task_id):
    task = CompressTask.query.get(task_id)
    if not task:
        return fail(message='任务不存在', code=404, http_status=404)
        
    d = task.to_dict()
    stages = CompressStage.query.filter_by(task_id=task.id).all()
    d['stages'] = [s.to_dict() for s in stages]
    
    return success(data=d)

@compress_bp.get('/compress/tasks/<int:task_id>/logs')
def get_task_logs(task_id):
    # Log file path matches CompressTaskRunner logic
    log_file = f'/data/workspace/hdap-platform/backend/hdap-platform-backend/data/tasks/{task_id}/stdout.log'
    if os.path.exists(log_file):
        try:
            # Read only last 50KB to avoid huge payloads
            file_size = os.path.getsize(log_file)
            limit = 50 * 1024
            
            with open(log_file, 'rb') as f:
                if file_size > limit:
                    f.seek(-limit, 2) # Seek to end minus limit
                    content = f.read().decode('utf-8', errors='replace')
                    content = "... (logs truncated due to size) ...\n" + content
                else:
                    content = f.read().decode('utf-8', errors='replace')
                    
            return success(data={'logs': content})
        except Exception as e:
            logger.error(f"Failed to read logs for task {task_id}: {e}")
            return success(data={'logs': f'Error reading logs: {str(e)}'})
            
    return success(data={'logs': 'No logs available yet.'})


@compress_bp.get('/compress/tasks/<int:task_id>/metrics')
def get_task_metrics(task_id):
    metric_file = f'/data/workspace/hdap-platform/backend/hdap-platform-backend/data/tasks/{task_id}/metrics.json'
    if os.path.exists(metric_file):
        try:
            with open(metric_file, 'r') as f:
                metrics = json.load(f)
            
            # Clean NaN/Inf in existing metrics
            def clean_nans(obj):
                import math
                if isinstance(obj, float):
                    if math.isnan(obj) or math.isinf(obj):
                        return None
                    return obj
                elif isinstance(obj, dict):
                    return {k: clean_nans(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_nans(v) for v in obj]
                return obj
                
            metrics = clean_nans(metrics)
            return success(data=metrics)
        except:
            return success(data=[])
    return success(data=[])


@compress_bp.post('/compress/tasks')
def create_compress_task():
    try:
        body = request.json or {}
        logger.info(f"Received create task request: {body}")
        
        name = (body.get('name') or '').strip()
        model_name = (body.get('modelName') or '').strip()
        device_type = (body.get('deviceType') or '').strip() or None
        stage = (body.get('stage') or '').strip() or 'pruning'
    
        if not name:
            logger.warning("Missing task name")
            return fail(message='缺少任务名称', code=400, http_status=400)
        if not model_name:
            logger.warning("Missing model name")
            return fail(message='缺少模型名称', code=400, http_status=400)
    
        if device_type:
            try:
                exists = bool(Device.query.filter_by(type=device_type).first())
            except Exception as e:
                logger.error(f"Error checking device type: {e}")
                exists = True  # 容错：设备库查询异常时不阻断创建
            if not exists:
                logger.warning(f"Device type not found: {device_type}")
                return fail(message='设备类型不存在于设备库', code=400, http_status=400)
    
        task = CompressTask(
            name=name,
            model_name=model_name,
            device_type=device_type,
            status='pending',
        )
        db.session.add(task)
        db.session.flush()
    
        stages = []
    
        def _new_stage(ph: str):
            return CompressStage(
                task_id=task.id,
                phase=ph,
                status='pending',
                compression_algo=(body.get('compressionAlgo') or '').strip() or None,
                algo_params=(body.get('algoParams') or '').strip() or None,
                eval_metric=(body.get('evalMetric') or '').strip() or None,
                latency_budget=body.get('latencyBudget'),
                accuracy_loss_limit=body.get('accuracyLossLimit'),
            )
    
        if stage == 'pruning':
            stages.append(_new_stage('pruning'))
        elif stage == 'finetune':
            stages.append(_new_stage('finetune'))
        else:
            stages.append(_new_stage('pruning'))
            stages.append(_new_stage('finetune'))
    
        for s in stages:
            db.session.add(s)
    
        db.session.commit()
        logger.info(f"Task created successfully: {task.id}")
    
        d = task.to_dict()
        d['stages'] = [s.to_dict() for s in stages]
        return success(data=d, message='已创建压缩任务')
    except Exception as e:
        logger.error(f"Failed to create task: {e}", exc_info=True)
        db.session.rollback()
        return fail(message=f"任务创建失败: {str(e)}", code=500, http_status=500)


@compress_bp.post('/compress/tasks/<int:task_id>/start')
def start_compress_task(task_id):
    try:
        task = CompressTask.query.get(task_id)
        if not task:
            return fail(message='任务不存在', code=404, http_status=404)
        
        if task.status == 'running':
            return success(message='任务已在运行中')
    
        task.status = 'running'
        stages = CompressStage.query.filter_by(task_id=task.id).all()
        for s in stages:
            if s.status == 'pending':
                s.status = 'running'
                s.progress = 0
        
        db.session.commit()
        
        # Start background task
        try:
            CompressTaskRunner.run_task(task.id)
        except Exception as e:
            logger.error(f"Failed to trigger background task: {e}", exc_info=True)
            # Revert status if thread failed to start
            task.status = 'failed'
            db.session.commit()
            return fail(message=f'任务启动失败: {str(e)}', code=500, http_status=500)
        
        return success(message='任务已启动')
    except Exception as e:
        logger.error(f"Error in start_compress_task: {e}", exc_info=True)
        return fail(message=f'启动请求异常: {str(e)}', code=500, http_status=500)


@compress_bp.post('/compress/tasks/<int:task_id>/stop')
def stop_compress_task(task_id):
    task = CompressTask.query.get(task_id)
    if not task:
        return fail(message='任务不存在', code=404, http_status=404)
        
    if task.status not in ['running', 'pending']:
        return success(message='任务未在运行')

    task.status = 'aborted'
    stages = CompressStage.query.filter_by(task_id=task.id).all()
    for s in stages:
        if s.status in ['running', 'pending']:
            s.status = 'aborted'
    
    db.session.commit()
    
    return success(message='任务已请求中止')


@compress_bp.delete('/compress/tasks/<int:task_id>')
def delete_compress_task(task_id):
    task = CompressTask.query.get(task_id)
    if not task:
        return fail(message='任务不存在', code=404, http_status=404)
        
    if task.status == 'running':
        return fail(message='无法删除运行中的任务', code=400, http_status=400)
        
    # Delete associated stages
    CompressStage.query.filter_by(task_id=task.id).delete()
    
    # Delete task directory if needed? 
    # For now we keep files or let user clean up manually, or we could rm -rf.
    # Safe to just delete DB record.
    
    db.session.delete(task)
    db.session.commit()
    
    return success(message='任务已删除')


@compress_bp.get('/compress/tasks/defaults')
def get_task_defaults():
    model_name = (request.args.get('modelName') or '').strip()
    algo = (request.args.get('compressionAlgo') or 'HDAP').strip()
    
    # 1. Global Defaults
    defaults = {
        'train_epochs': 5,
        'batch_size': 64,
        'lr': 0.01,
    }
    
    # 2. Algorithm Defaults
    if algo == 'HDAP':
        defaults.update({
            'target_ratio': 50,
            'pop_size': 10,
            'generations': 30,
            'iterations': 5
        })
    elif algo == 'Grid Search':
        defaults.update({
            'iterations': 2,
            'pop_size': 10,
            'generations': 10,
            'grid_min': 0.1,
            'grid_max': 0.9,
            'grid_step': 0.1
            # 'prune_rate_grid': '0.1, 0.2, 0.3, 0.4, 0.5' # Use dynamic generation instead
        })
        
    # 3. Model Defaults
    if model_name:
        try:
            from app.models.model import Model, ModelVersion
            from app.core.compression.loader import ModelLoader
            
            m = Model.query.filter_by(name=model_name).first()
            if m:
                v = ModelVersion.query.filter_by(model_id=m.id).first()
                if v and v.definition_path:
                    model_params = ModelLoader.extract_default_params(v.definition_path)
                    defaults.update(model_params)
                elif model_name == 'resnet56': # Fallback
                     definition_path = '/data/workspace/cluster-compression/benchmarks/engine/models/cifar/resnet_tiny.py'
                     model_params = ModelLoader.extract_default_params(definition_path)
                     defaults.update(model_params)
        except Exception as e:
            pass # Ignore model loading errors for defaults
            
    return success(data=defaults)


@compress_bp.get('/compress/models/<model_name>/params')
def get_model_params(model_name):
    """
    Get default training parameters for a model from its definition file.
    """
    try:
        # Find model version
        # We reuse logic from ModelLoader but we need definition path
        # Assuming we want the default version or the one associated with the model name
        
        # Simplified lookup: get first version with definition
        from app.models.model import Model, ModelVersion
        from app.core.compression.loader import ModelLoader
        
        m = Model.query.filter_by(name=model_name).first()
        if not m:
             # Fallback for resnet56 hardcoded in loader
             if model_name == 'resnet56':
                 definition_path = '/data/workspace/cluster-compression/benchmarks/engine/models/cifar/resnet_tiny.py'
                 defaults = ModelLoader.extract_default_params(definition_path)
                 return success(data=defaults)
             return fail(message='Model not found')
             
        v = ModelVersion.query.filter_by(model_id=m.id).first()
        if not v or not v.definition_path:
             # Fallback check again
             if model_name == 'resnet56':
                 definition_path = '/data/workspace/cluster-compression/benchmarks/engine/models/cifar/resnet_tiny.py'
                 defaults = ModelLoader.extract_default_params(definition_path)
                 return success(data=defaults)
             return success(data={})
             
        defaults = ModelLoader.extract_default_params(v.definition_path)
        return success(data=defaults)
        
    except Exception as e:
        return fail(message=str(e))


@compress_bp.get('/compress/tasks/summary')
def compress_summary():
    total = CompressTask.query.count()
    running = CompressTask.query.filter_by(status='running').count()
    succeeded = CompressTask.query.filter_by(status='succeeded').count()
    failed = CompressTask.query.filter_by(status='failed').count()
    pending = CompressTask.query.filter_by(status='pending').count()
    stage_total = CompressStage.query.count()
    pruning_total = CompressStage.query.filter_by(phase='pruning').count()
    finetune_total = CompressStage.query.filter_by(phase='finetune').count()
    pruning_running = CompressStage.query.filter_by(phase='pruning', status='running').count()
    finetune_running = CompressStage.query.filter_by(phase='finetune', status='running').count()

    data = {
        'total': total,
        'running': running,
        'succeeded': succeeded,
        'failed': failed,
        'pending': pending,
        'stageTotal': stage_total,
        'pruningTotal': pruning_total,
        'finetuneTotal': finetune_total,
        'pruningRunning': pruning_running,
        'finetuneRunning': finetune_running,
    }
    return success(data=data)
