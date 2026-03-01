
import json
from app import create_app
from app.models.surrogate_task import SurrogateTask
from app.models.surrogate_pipeline import SurrogatePipeline

def find_task():
    app = create_app()
    with app.app_context():
        # Search for task by exact name first
        name = "ResNet-Tiny-56-Jetson Xavier NX-Task"
        print(f"Searching for task/pipeline with name: {name}")
        
        # Check Pipelines
        pipeline = SurrogatePipeline.query.filter(SurrogatePipeline.name.like(f"%{name}%")).first()
        if pipeline:
            print(f"Found Pipeline: ID {pipeline.id}, Name: {pipeline.name}")
            print(f"  Collect Task ID: {pipeline.collect_task_id}")
            collect_task = SurrogateTask.query.get(pipeline.collect_task_id)
        else:
            # Check Tasks directly
            collect_task = SurrogateTask.query.filter(SurrogateTask.name.like(f"%{name}%"), SurrogateTask.type == 'collect').order_by(SurrogateTask.created_at.desc()).first()
            
        if collect_task:
            print(f"Found Collect Task: ID {collect_task.id}, Name: {collect_task.name}")
            print(f"  Dataset Size: {collect_task.dataset_size}")
            if collect_task.training_params:
                params = json.loads(collect_task.training_params)
                print(f"  Sample Count in Params: {params.get('sample_count')}")
                metrics = params.get('collection_metrics', [])
                print(f"  Current Metrics Count: {len(metrics)}")
        else:
            print("Collect task not found via pipeline or direct name search.")
            
            # List all collect tasks to help identify
            tasks = SurrogateTask.query.filter_by(type='collect').order_by(SurrogateTask.created_at.desc()).limit(10).all()
            print("\nRecent Collect Tasks:")
            for t in tasks:
                print(f"  ID: {t.id}, Name: {t.name}, Created: {t.created_at}")

if __name__ == "__main__":
    find_task()
