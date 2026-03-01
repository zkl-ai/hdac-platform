
import sys
import os
import json
from app import create_app
from app.models.surrogate_task import SurrogateTask
from app.models.surrogate_pipeline import SurrogatePipeline

app = create_app()

with app.app_context():
    # Get latest pipeline
    pipeline = SurrogatePipeline.query.order_by(SurrogatePipeline.created_at.desc()).first()
    if not pipeline:
        print("No pipelines found")
        sys.exit(0)
        
    print(f"Pipeline ID: {pipeline.id}, Status: {pipeline.status}")
    
    if pipeline.collect_task_id:
        task = SurrogateTask.query.get(pipeline.collect_task_id)
        print(f"Collect Task ID: {task.id}, Status: {task.status}")
        print(f"Device List: {task.device_list}")
        
        if task.training_params:
            try:
                params = json.loads(task.training_params)
                print("Training Params Keys:", params.keys())
                if 'collection_metrics' in params:
                    print(f"Collection Metrics Count: {len(params['collection_metrics'])}")
                    if len(params['collection_metrics']) > 0:
                        print("Last metric:", params['collection_metrics'][-1])
                else:
                    print("No collection_metrics in params")
                    
                if 'sample_count' in params:
                    print(f"Sample Count: {params['sample_count']}")
                else:
                    print("No sample_count in params")
            except Exception as e:
                print(f"Error parsing params: {e}")
        else:
            print("No training params")
    else:
        print("No collect task")
