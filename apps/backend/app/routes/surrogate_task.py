from flask import Blueprint, request
from app.extensions import db
from app.utils.response import success, fail
from app.models.surrogate_task import SurrogateTask
from app.models.surrogate_pipeline import SurrogatePipeline
from app.services.cluster_service import ClusterService
from app.services.collection_service import CollectionService
from app.services.training_service import TrainingService
import threading
import time
import random
import json
from sqlalchemy import or_

surrogate_bp = Blueprint('surrogate_task', __name__, url_prefix='/api')


@surrogate_bp.get('/surrogate/tasks')
def list_tasks():
    q = SurrogateTask.query
    kw = (request.args.get('keyword') or '').strip()
    t = (request.args.get('type') or '').strip()
    st = (request.args.get('status') or '').strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(SurrogateTask.name.like(like))
    if t:
        q = q.filter_by(type=t)
    if st:
        q = q.filter_by(status=st)
    items = [it.to_dict() for it in q.order_by(SurrogateTask.created_at.desc()).all()]
    return success(data={'items': items})


@surrogate_bp.post('/surrogate/tasks')
def create_task():
    body = request.json or {}
    name = (body.get('name') or '').strip()
    t = (body.get('type') or '').strip() or 'collect'
    if not name:
        return fail(message='缺少 name', code=400, http_status=400)
    task = SurrogateTask(
        name=name,
        type=t,
        dnn_model_name=(body.get('dnnModelName') or '').strip() or None,
        surrogate_structure=(body.get('surrogateStructure') or '').strip() or None,
        device_list=(body.get('deviceList') or '').strip() or None,
        dataset_size=body.get('datasetSize'),
        training_params=(body.get('trainingParams') or '').strip() or None,
        mape=body.get('mape'),
        accel_effect=(body.get('accelEffect') or '').strip() or None,
        status='pending',
    )
    db.session.add(task)
    db.session.commit()
    return success(data=task.to_dict(), message='已创建')


def _run_service_async(task_id, service_func):
    """Helper to run service in a thread context"""
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            service_func(task_id)
        except Exception as e:
            print(f"Task {task_id} failed: {e}")
            task = SurrogateTask.query.get(task_id)
            if task:
                task.status = 'failed'
                db.session.commit()

@surrogate_bp.post('/surrogate/tasks/<int:tid>/run')
def run_task(tid: int):
    task = SurrogateTask.query.get(tid)
    if not task:
        return fail(message='任务不存在', code=404, http_status=404)
    
    if task.status == 'running':
        return success(data=task.to_dict(), message='任务已在运行')
        
    # Find pipeline to propagate params
    pipeline = SurrogatePipeline.query.filter(
        or_(
            SurrogatePipeline.cluster_task_id == tid,
            SurrogatePipeline.collect_task_id == tid,
            SurrogatePipeline.train_task_id == tid
        )
    ).first()
    
    # Propagate params from upstream
    if pipeline:
        current_params = {}
        if task.training_params:
            try:
                current_params = json.loads(task.training_params)
            except:
                pass
                
        if task.type == 'collect' and pipeline.cluster_task_id:
            cluster_task = SurrogateTask.query.get(pipeline.cluster_task_id)
            if cluster_task and cluster_task.training_params:
                try:
                    c_params = json.loads(cluster_task.training_params)
                    if 'cluster_mapping' in c_params:
                        current_params['cluster_mapping'] = c_params['cluster_mapping']
                        task.training_params = json.dumps(current_params, ensure_ascii=False)
                except:
                    pass
                    
        elif task.type == 'train':
            if pipeline.cluster_task_id:
                cluster_task = SurrogateTask.query.get(pipeline.cluster_task_id)
                if cluster_task and cluster_task.training_params:
                    try:
                        c_params = json.loads(cluster_task.training_params)
                        if 'cluster_mapping' in c_params:
                            current_params['cluster_mapping'] = c_params['cluster_mapping']
                    except:
                        pass
            if pipeline.collect_task_id:
                # Tell training service where the data is (in the collection task's folder)
                current_params['data_source_task_id'] = pipeline.collect_task_id
            
            task.training_params = json.dumps(current_params, ensure_ascii=False)
            
    task.status = 'running'
    task.progress = 0
    db.session.commit()
    
    # Dispatch
    if task.type == 'cluster':
        threading.Thread(target=_run_service_async, args=(tid, ClusterService.run_clustering)).start()
    elif task.type == 'collect':
        # Collection service handles its own threading/async usually, but we wrap it to be safe
        threading.Thread(target=_run_service_async, args=(tid, CollectionService.run_collection)).start()
    elif task.type == 'train':
        threading.Thread(target=_run_service_async, args=(tid, TrainingService.run_training)).start()
    else:
        # Fallback
        pass

    return success(data=task.to_dict(), message='已启动任务')


def _run_pipeline_orchestrator(pid):
    """
    Orchestrates the execution of a pipeline: Cluster -> Collect -> Train
    """
    from app import create_app
    app = create_app()
    with app.app_context():
        pipeline = SurrogatePipeline.query.get(pid)
        if not pipeline:
            return
            
        pipeline.status = 'running'
        db.session.commit()
        
        # Helper to wait for task
        def wait_for_task(tid):
            while True:
                db.session.commit()
                t = SurrogateTask.query.get(tid)
                if not t: return False
                if t.status == 'succeeded': return True
                if t.status == 'failed': return False
                time.sleep(1)
        
        try:
            # 1. Cluster
            if pipeline.cluster_task_id:
                print(f"Pipeline {pid}: Starting Cluster Task {pipeline.cluster_task_id}")
                # We reuse run_task logic by calling the service directly? 
                # Better to use the API logic but we are internal.
                # Let's call the service directly.
                t = SurrogateTask.query.get(pipeline.cluster_task_id)
                t.status = 'running'
                db.session.commit()
                ClusterService.run_clustering(pipeline.cluster_task_id)
                
                if not wait_for_task(pipeline.cluster_task_id):
                    raise Exception("Cluster task failed")
                    
            # 2. Collect
            if pipeline.collect_task_id:
                print(f"Pipeline {pid}: Starting Collect Task {pipeline.collect_task_id}")
                
                # Propagate params (Cluster -> Collect)
                if pipeline.cluster_task_id:
                    cluster_task = SurrogateTask.query.get(pipeline.cluster_task_id)
                    collect_task = SurrogateTask.query.get(pipeline.collect_task_id)
                    if cluster_task and collect_task:
                        try:
                            c_params = json.loads(cluster_task.training_params or '{}')
                            cur_params = json.loads(collect_task.training_params or '{}')
                            if 'cluster_mapping' in c_params:
                                cur_params['cluster_mapping'] = c_params['cluster_mapping']
                                collect_task.training_params = json.dumps(cur_params, ensure_ascii=False)
                                db.session.commit()
                        except: pass

                # Run Collection
                # CollectionService.run_collection spawns a thread, but we want to wait for the RESULT (metrics received)
                # So we call it, then wait loop.
                CollectionService.run_collection(pipeline.collect_task_id)
                
                if not wait_for_task(pipeline.collect_task_id):
                    raise Exception("Collection task failed")

            # 3. Train
            if pipeline.train_task_id:
                print(f"Pipeline {pid}: Starting Train Task {pipeline.train_task_id}")
                
                # Propagate params (Cluster/Collect -> Train)
                train_task = SurrogateTask.query.get(pipeline.train_task_id)
                current_params = json.loads(train_task.training_params or '{}')
                
                if pipeline.cluster_task_id:
                    cluster_task = SurrogateTask.query.get(pipeline.cluster_task_id)
                    if cluster_task:
                        try:
                            c_params = json.loads(cluster_task.training_params or '{}')
                            if 'cluster_mapping' in c_params:
                                current_params['cluster_mapping'] = c_params['cluster_mapping']
                        except: pass
                        
                if pipeline.collect_task_id:
                    current_params['data_source_task_id'] = pipeline.collect_task_id
                    
                    collect_task = SurrogateTask.query.get(pipeline.collect_task_id)
                    if collect_task and collect_task.training_params:
                        try:
                            col_params = json.loads(collect_task.training_params)
                            if 'collection_result_path' in col_params:
                                current_params['collection_result_path'] = col_params['collection_result_path']
                        except: pass
                    
                train_task.training_params = json.dumps(current_params, ensure_ascii=False)
                train_task.status = 'running'
                db.session.commit()
                
                # Run Training
                TrainingService.run_training(pipeline.train_task_id)
                
                if not wait_for_task(pipeline.train_task_id):
                    raise Exception("Training task failed")
            
            pipeline.status = 'succeeded'
            db.session.commit()
            
        except Exception as e:
            print(f"Pipeline {pid} failed: {e}")
            pipeline.status = 'failed'
            db.session.commit()


@surrogate_bp.post('/surrogate/pipelines/<int:pid>/start')
def start_pipeline(pid: int):
    pipeline = SurrogatePipeline.query.get(pid)
    if not pipeline:
        return fail(message='Pipeline not found', code=404, http_status=404)
        
    if pipeline.status == 'running':
        return success(message='Pipeline already running')
        
    # Reset subtasks status if needed? 
    # Or just start. Let's assume re-run is allowed.
    
    threading.Thread(target=_run_pipeline_orchestrator, args=(pid,), daemon=True).start()
    return success(message='Pipeline execution started')


@surrogate_bp.get('/surrogate/tasks/<int:tid>/status')
def task_status(tid: int):
    task = SurrogateTask.query.get(tid)
    if not task:
        return fail(message='任务不存在', code=404, http_status=404)
    return success(data={'status': task.status, 'progress': task.progress, 'mape': task.mape, 'accelEffect': task.accel_effect})


@surrogate_bp.post('/surrogate/tasks/mock')
def mock_tasks():
    return success(message='Mock 功能已禁用')


@surrogate_bp.get('/surrogate/tasks/summary')
def task_summary():
    # Calculate stats from SurrogatePipeline in DB
    pipelines = SurrogatePipeline.query.all()
    
    total = len(pipelines)
    running = sum(1 for x in pipelines if x.status == 'running')
    pending = sum(1 for x in pipelines if x.status == 'pending')
    succeeded = sum(1 for x in pipelines if x.status == 'succeeded')
    failed = sum(1 for x in pipelines if x.status == 'failed')

    # For byType stats, we look at SurrogateTask
    tasks = SurrogateTask.query.all()
    
    by_type = {
        'collect': 0,
        'train': 0,
        'evaluate': 0,
        'cluster': 0,
    }
    
    by_type_status = {
        'cluster': {'total': 0, 'running': 0, 'notRunning': 0},
        'collect': {'total': 0, 'running': 0, 'notRunning': 0},
        'train': {'total': 0, 'running': 0, 'notRunning': 0},
    }
    
    for t in tasks:
        if t.type in by_type:
            by_type[t.type] += 1
            
        if t.type in by_type_status:
            by_type_status[t.type]['total'] += 1
            if t.status == 'running':
                by_type_status[t.type]['running'] += 1
            else:
                by_type_status[t.type]['notRunning'] += 1

    data = {
        'total': total,
        'running': running,
        'pending': pending,
        'succeeded': succeeded,
        'failed': failed,
        'byType': by_type,
        'byTypeStatus': by_type_status
    }
    return success(data=data)


@surrogate_bp.get('/surrogate/pipelines/detail')
def get_pipeline_detail():
    pid = request.args.get('id')
    if not pid:
        return fail(message='Missing id', code=400, http_status=400)
    
    try:
        pid = int(pid)
    except:
        return fail(message='Invalid id', code=400, http_status=400)

    # 1. Try match Pipeline ID
    pipeline = SurrogatePipeline.query.get(pid)
    
    # 2. If not found, try match subtask ID
    if not pipeline:
        pipeline = SurrogatePipeline.query.filter(
            or_(
                SurrogatePipeline.cluster_task_id == pid,
                SurrogatePipeline.collect_task_id == pid,
                SurrogatePipeline.train_task_id == pid
            )
        ).first()

    if not pipeline:
        return fail(message='Pipeline not found', code=404, http_status=404)

    # Reuse the logic from list_pipelines to build the dict
    # We should probably refactor this into a helper method on SurrogatePipeline model or here
    # For now, duplicate logic for safety/speed
    
    # Resolve subtasks
    t_ids = [pipeline.cluster_task_id, pipeline.collect_task_id, pipeline.train_task_id]
    t_ids = [x for x in t_ids if x is not None]
    
    tasks_map = {}
    if t_ids:
        tasks = SurrogateTask.query.filter(SurrogateTask.id.in_(t_ids)).all()
        tasks_map = {t.id: t for t in tasks}
        
    subtasks = []
    if pipeline.cluster_task_id and pipeline.cluster_task_id in tasks_map:
        t = tasks_map[pipeline.cluster_task_id]
        d = t.to_dict()
        d['phase'] = 'cluster'
        subtasks.append(d)
    if pipeline.collect_task_id and pipeline.collect_task_id in tasks_map:
        t = tasks_map[pipeline.collect_task_id]
        d = t.to_dict()
        d['phase'] = 'collect'
        subtasks.append(d)
    if pipeline.train_task_id and pipeline.train_task_id in tasks_map:
        t = tasks_map[pipeline.train_task_id]
        d = t.to_dict()
        d['phase'] = 'train'
        subtasks.append(d)
        
    p_dict = pipeline.to_dict()
    p_dict['taskName'] = f"{pipeline.model_name}-{pipeline.device_type}-Task"
    p_dict['subtasks'] = subtasks
    
    return success(data=p_dict)


@surrogate_bp.get('/surrogate/pipelines')
def list_pipelines():
    q = SurrogatePipeline.query
    
    keyword = (request.args.get('keyword') or '').strip()
    model_name = (request.args.get('modelName') or '').strip()
    device_type = (request.args.get('deviceType') or '').strip()
    status_list = request.args.getlist('status')
    if not status_list and request.args.get('status'):
        status_list = [request.args.get('status')]
    
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                SurrogatePipeline.model_name.like(like),
                SurrogatePipeline.device_type.like(like)
            )
        )
        
    if model_name:
        q = q.filter(SurrogatePipeline.model_name == model_name)
        
    if device_type:
        q = q.filter(SurrogatePipeline.device_type == device_type)
        
    if status_list:
        q = q.filter(SurrogatePipeline.status.in_(status_list))
        
    items = q.order_by(SurrogatePipeline.created_at.desc()).all()
    
    results = []
    for p in items:
        # Resolve subtasks
        t_ids = [p.cluster_task_id, p.collect_task_id, p.train_task_id]
        t_ids = [x for x in t_ids if x is not None]
        
        tasks_map = {}
        if t_ids:
            tasks = SurrogateTask.query.filter(SurrogateTask.id.in_(t_ids)).all()
            tasks_map = {t.id: t for t in tasks}
            
        subtasks = []
        if p.cluster_task_id and p.cluster_task_id in tasks_map:
            t = tasks_map[p.cluster_task_id]
            d = t.to_dict()
            d['phase'] = 'cluster'
            subtasks.append(d)
        if p.collect_task_id and p.collect_task_id in tasks_map:
            t = tasks_map[p.collect_task_id]
            d = t.to_dict()
            d['phase'] = 'collect'
            subtasks.append(d)
        if p.train_task_id and p.train_task_id in tasks_map:
            t = tasks_map[p.train_task_id]
            d = t.to_dict()
            d['phase'] = 'train'
            subtasks.append(d)
            
        p_dict = p.to_dict()
        p_dict['taskName'] = f"{p.model_name}-{p.device_type}-Task"
        p_dict['subtasks'] = subtasks
        
        # Infer createdBy from subtasks
        creator = None
        for s in subtasks:
            if s.get('createdBy') and s.get('createdBy') != 'None':
                creator = s.get('createdBy')
                break
        p_dict['createdBy'] = creator or 'alice_admin'
        
        results.append(p_dict)
        
    return success(data={'items': results})


@surrogate_bp.delete('/surrogate/pipelines/<int:pid>')
def delete_pipeline(pid):
    p = SurrogatePipeline.query.get(pid)
    if not p:
        return fail(message='Pipeline not found', code=404, http_status=404)
        
    # Delete associated subtasks
    t_ids = [p.cluster_task_id, p.collect_task_id, p.train_task_id]
    for tid in t_ids:
        if tid:
            t = SurrogateTask.query.get(tid)
            if t:
                db.session.delete(t)
                
    db.session.delete(p)
    db.session.commit()
    return success(message='Deleted')


@surrogate_bp.post('/surrogate/pipelines')
def create_pipeline():
    body = request.json or {}
    model_name = (body.get('modelName') or '').strip()
    device_type = (body.get('deviceType') or '').strip()
    dataset_name = (body.get('datasetName') or '').strip() or None
    task_name = (body.get('taskName') or '').strip() or None
    device_list = body.get('deviceList') or [] # List of IPs
    
    if not model_name or not device_type:
        return fail(message='缺少必要字段: modelName / deviceType', code=400, http_status=400)
    
    # Store device list as comma-separated string in task.device_list
    device_list_str = ','.join(device_list) if device_list else None
    
    cluster = SurrogateTask(name=f'聚类-{model_name}-{device_type}', type='cluster', status='pending', device_list=device_list_str, dnn_model_name=model_name)
    collect = SurrogateTask(name=f'采集-{model_name}-{device_type}', type='collect', status='pending', device_list=device_list_str, dnn_model_name=model_name)
    train = SurrogateTask(name=f'训练-{model_name}-{device_type}', type='train', status='pending', device_list=device_list_str, dnn_model_name=model_name)
    db.session.add_all([cluster, collect, train])
    db.session.flush()
    
    params_payload = {
        'taskName': task_name,
        'pipelineName': (f'{task_name}-{model_name}' if task_name else model_name),
        'modelName': model_name,
        'deviceType': device_type,
        'targetDeviceList': device_list # Also store in JSON params for clarity
    }
    try:
        payload_str = json.dumps(params_payload, ensure_ascii=False)
        cluster.training_params = payload_str
        collect.training_params = payload_str
        train.training_params = payload_str
    except Exception:
        pass
    pipe = SurrogatePipeline(
        model_name=model_name,
        device_type=device_type,
        dataset_name=dataset_name,
        cluster_task_id=cluster.id,
        collect_task_id=collect.id,
        train_task_id=train.id,
        status='pending',
    )
    db.session.add(pipe)
    db.session.commit()
    d = pipe.to_dict()
    d['subtasks'] = [
        {**cluster.to_dict(), 'phase': 'cluster'},
        {**collect.to_dict(), 'phase': 'collect'},
        {**train.to_dict(), 'phase': 'train'},
    ]
    return success(message='已创建构建任务', data=d)
