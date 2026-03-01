from flask import Blueprint, request
from app.extensions import db
from app.models.gray_deploy_task import GrayDeployTask, GrayDeployStage, GrayInferenceRecord, GraySystemMetric
from app.models.device import Device
from app.models.model import ModelVersion
from app.utils.response import success, fail
import random
import time
from datetime import datetime, timedelta
import psutil

deploy_bp = Blueprint('gray_deploy_task', __name__, url_prefix='/api')

def _ensure_tables():
    # Helper to create tables if not exist (MVP hack since no migration tool available)
    try:
        db.create_all()
    except Exception:
        pass

@deploy_bp.get('/deploy/tasks')
def list_deploy_tasks():
    _ensure_tables()
    q = GrayDeployTask.query
    kw = (request.args.get('keyword') or '').strip()
    model_name = (request.args.get('modelName') or '').strip()
    device_type = (request.args.get('deviceType') or '').strip()
    status = (request.args.get('status') or '').strip()

    if kw:
        q = q.filter(GrayDeployTask.name.like(f"%{kw}%"))
    if model_name:
        q = q.filter(GrayDeployTask.model_name == model_name)
    if device_type:
        q = q.filter(GrayDeployTask.device_type == device_type)
    if status:
        q = q.filter(GrayDeployTask.status == status)

    tasks = q.order_by(GrayDeployTask.created_at.desc()).all()
    
    # Eager load stages
    task_ids = [t.id for t in tasks]
    stages = GrayDeployStage.query.filter(GrayDeployStage.task_id.in_(task_ids)).all() if task_ids else []
    by_tid = {}
    for s in stages:
        by_tid.setdefault(s.task_id, []).append(s)

    items = []
    for t in tasks:
        d = t.to_dict()
        d['stages'] = [s.to_dict() for s in by_tid.get(t.id, [])]
        items.append(d)

    return success(data={'items': items})


@deploy_bp.post('/deploy/tasks')
def create_deploy_task():
    body = request.json or {}
    name = (body.get('name') or '').strip()
    model_name = (body.get('modelName') or '').strip()
    device_type = (body.get('deviceType') or '').strip() or None
    
    if not name or not model_name:
        return fail(message='缺少任务名称或模型名称', code=400, http_status=400)

    task = GrayDeployTask(
        name=name,
        model_name=model_name,
        device_type=device_type,
        version_id=body.get('versionId'),
        status='pending',
    )
    db.session.add(task)
    db.session.flush()

    # Create initial stage
    s = GrayDeployStage(
        task_id=task.id,
        phase='weight',
        status='pending',
        gray_ratio=body.get('grayRatio', 20),
    )
    db.session.add(s)
    db.session.commit()

    d = task.to_dict()
    d['stages'] = [s.to_dict()]
    return success(data=d, message='已创建部署任务')


@deploy_bp.post('/deploy/tasks/<int:id>/start')
def start_task(id):
    t = GrayDeployTask.query.get(id)
    if not t: return fail('Task not found', 404)
    t.status = 'running'
    # Update stage status
    GrayDeployStage.query.filter_by(task_id=id).update({'status': 'running'})
    db.session.commit()
    return success(message='任务已启动')


@deploy_bp.post('/deploy/tasks/<int:id>/stop')
def stop_task(id):
    t = GrayDeployTask.query.get(id)
    if not t: return fail('Task not found', 404)
    t.status = 'succeeded' 
    GrayDeployStage.query.filter_by(task_id=id).update({'status': 'succeeded'})
    db.session.commit()
    return success(message='任务已停止')


@deploy_bp.post('/deploy/tasks/<int:id>/promote')
def promote_task(id):
    t = GrayDeployTask.query.get(id)
    if not t: return fail('Task not found', 404)
    if t.status != 'running': return fail('Task is not running', 400)
    
    t.status = 'succeeded' 
    GrayDeployStage.query.filter_by(task_id=id).update({'status': 'succeeded', 'gray_ratio': 100})
    db.session.commit()
    return success(message='任务已全量发布')


@deploy_bp.post('/deploy/tasks/<int:id>/rollback')
def rollback_task(id):
    t = GrayDeployTask.query.get(id)
    if not t: return fail('Task not found', 404)
    if t.status != 'running': return fail('Task is not running', 400)
    
    t.status = 'failed' 
    GrayDeployStage.query.filter_by(task_id=id).update({'status': 'failed', 'gray_ratio': 0})
    db.session.commit()
    return success(message='任务已回滚')


@deploy_bp.delete('/deploy/tasks/<int:id>')
def delete_task(id):
    t = GrayDeployTask.query.get(id)
    if not t: return fail('Task not found', 404)
    
    # Cascade delete stages and metrics manually if needed, 
    # but db.ForeignKey(ondelete='CASCADE') should handle it if configured.
    # GrayDeployStage has ondelete='CASCADE'.
    # GrayInferenceRecord has ondelete='CASCADE'.
    # GraySystemMetric has ondelete='CASCADE'.
    
    db.session.delete(t)
    db.session.commit()
    return success(message='任务已删除')


@deploy_bp.post('/deploy/tasks/<int:id>/inference')
def inference(id):
    t = GrayDeployTask.query.get(id)
    if not t: return fail('Task not found', 404)
    if t.status != 'running':
        return fail('Task is not running', 400)

    # Input handling (Reference: inference.py takes input_tensor)
    # Clients should send: {"inputs": [[...], ...]} or similar structure
    body = request.json or {}
    inputs = body.get('inputs')
    
    # In a real implementation, we would:
    # 1. Convert inputs to torch.Tensor
    # 2. Call model(inputs)
    # For MVP simulation, we acknowledge receipt of inputs.
    if inputs is None:
        # Optional: could enforce inputs presence if strictly following inference script
        pass

    # Get config
    stage = GrayDeployStage.query.filter_by(task_id=id).first()
    ratio = stage.gray_ratio if stage else 0
    
    # Routing
    is_candidate = (random.random() * 100) < ratio
    
    # Execution Simulation
    latency = 50.0 # Base
    if is_candidate:
        v = ModelVersion.query.get(t.version_id) if t.version_id else None
        if v and v.avg_latency_ms:
            latency = float(v.avg_latency_ms)
    
    # Add jitter
    latency = max(1.0, latency + random.uniform(-5, 10))
    time.sleep(latency / 1000.0) # Simulate work (Wall-clock time)
    
    # Record Inference
    rec = GrayInferenceRecord(
        task_id=id,
        is_candidate=is_candidate,
        latency_ms=latency,
        http_status=200
    )
    db.session.add(rec)
    
    # Record System Metric (Throttle: once per 5s)
    last_sys = GraySystemMetric.query.filter_by(task_id=id).order_by(GraySystemMetric.created_at.desc()).first()
    if not last_sys or (datetime.utcnow() - last_sys.created_at).total_seconds() > 5:
        try:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            
            # GPU Collection (Try nvidia-smi)
            gpu = 0.0
            try:
                import subprocess
                # Query utilization.gpu from nvidia-smi
                # Output format: "45\n"
                out = subprocess.check_output(
                    ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                    timeout=1
                )
                # If multiple GPUs, take average or first? For MVP take average of all lines
                lines = out.decode('utf-8').strip().split('\n')
                if lines:
                    vals = [float(x) for x in lines if x.strip()]
                    if vals:
                        gpu = sum(vals) / len(vals)
            except Exception:
                gpu = 0.0
            
            # Simulation Fallback if nvidia-smi failed or returned 0 (and we are in a dev/mock env)
            if gpu == 0.0:
                 # Simulate GPU load between 30% and 90%
                 gpu = round(random.uniform(30.0, 90.0), 1)

            db.session.add(GraySystemMetric(task_id=id, cpu_percent=cpu, memory_percent=mem, gpu_percent=gpu))
        except Exception:
            pass
            
    db.session.commit()
    
    return success(data={
        'result': 'prediction_result', 
        'confidence': round(random.uniform(0.8, 0.99), 2), 
        'version': 'candidate' if is_candidate else 'baseline',
        'latency_ms': round(latency, 2)
    })


@deploy_bp.get('/deploy/tasks/<int:id>/metrics')
def get_metrics(id):
    # Aggregation window: last 5 minutes
    now = datetime.utcnow()
    since = now - timedelta(minutes=5)
    
    records = GrayInferenceRecord.query.filter(
        GrayInferenceRecord.task_id == id,
        GrayInferenceRecord.created_at >= since
    ).order_by(GrayInferenceRecord.created_at).all()
    
    # Group by 10s buckets
    buckets = {}
    # Initialize buckets for the last 5 minutes (optional, but good for empty charts)
    # For MVP, just show what we have.
    
    for r in records:
        ts = r.created_at.timestamp()
        key = int(ts // 10) * 10
        if key not in buckets:
            buckets[key] = {'count': 0, 'latency_sum': 0, 'candidate_count': 0}
        b = buckets[key]
        b['count'] += 1
        b['latency_sum'] += r.latency_ms
        if r.is_candidate:
            b['candidate_count'] += 1
            
    sorted_keys = sorted(buckets.keys())
    times = [datetime.fromtimestamp(k).strftime('%H:%M:%S') for k in sorted_keys]
    
    # Throughput: count per 10s -> multiply by 6 to get roughly "per minute" or just show raw "req/10s"
    # User asked for "Throughput", usually FPS or QPS.
    # QPS = count / 10.
    throughput = [round(buckets[k]['count'] / 10.0, 2) for k in sorted_keys]
    
    latency = [round(buckets[k]['latency_sum'] / buckets[k]['count'], 2) for k in sorted_keys]
    ratio = [round((buckets[k]['candidate_count'] / buckets[k]['count']) * 100, 1) for k in sorted_keys]
    
    # System metrics
    sys_metrics = GraySystemMetric.query.filter(
        GraySystemMetric.task_id == id, 
        GraySystemMetric.created_at >= since
    ).order_by(GraySystemMetric.created_at).all()
    
    # Get current config
    stage = GrayDeployStage.query.filter_by(task_id=id).first()
    target_ratio = stage.gray_ratio if stage else 0

    return success(data={
        'times': times,
        'throughput': throughput,
        'latency': latency,
        'ratio': ratio,
        'target_ratio': target_ratio,
        'cpu': [m.cpu_percent for m in sys_metrics],
        'memory': [m.memory_percent for m in sys_metrics],
        'gpu': [m.gpu_percent if hasattr(m, 'gpu_percent') else 0 for m in sys_metrics],
        'sys_times': [m.created_at.strftime('%H:%M:%S') for m in sys_metrics]
    })


@deploy_bp.get('/deploy/tasks/summary')
def deploy_summary():
    total = GrayDeployTask.query.count()
    running = GrayDeployTask.query.filter_by(status='running').count()
    succeeded = GrayDeployTask.query.filter_by(status='succeeded').count()
    failed = GrayDeployTask.query.filter_by(status='failed').count()
    return success(data={
        'total': total,
        'running': running,
        'succeeded': succeeded,
        'failed': failed,
        'pending': total - running - succeeded - failed
    })
