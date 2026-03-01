
from app import create_app
from app.models.model import ModelVersion
from app.models.surrogate_pipeline import SurrogatePipeline
from app.models.surrogate_task import SurrogateTask
from app.extensions import db

app = create_app()
with app.app_context():
    print("Checking Data Integrity...")
    versions = ModelVersion.query.filter(ModelVersion.type == 'Surrogate').all()
    print(f"Found {len(versions)} Surrogate Model Versions.")
    
    for v in versions:
        print(f"\nVersion ID: {v.id}, Name: {v.name}, SourceTaskID: {v.source_task_id}")
        if not v.source_task_id:
            print("  -> ERROR: source_task_id is missing!")
            continue
            
        # Check if task exists
        task = SurrogateTask.query.get(v.source_task_id)
        if not task:
            print(f"  -> ERROR: Source Task {v.source_task_id} NOT FOUND in SurrogateTask table!")
            continue
            
        print(f"  -> Source Task found: {task.name} (Type: {task.type})")
        
        # Check if pipeline exists via subtask
        pipeline = SurrogatePipeline.query.filter(
            (SurrogatePipeline.cluster_task_id == v.source_task_id) |
            (SurrogatePipeline.collect_task_id == v.source_task_id) |
            (SurrogatePipeline.train_task_id == v.source_task_id)
        ).first()
        
        if pipeline:
            print(f"  -> Pipeline found: ID {pipeline.id}, Name: {pipeline.model_name}")
        else:
            print("  -> ERROR: Pipeline NOT FOUND for this task ID!")
            
    print("\nDone.")
