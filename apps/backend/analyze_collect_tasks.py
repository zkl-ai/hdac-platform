
import json
import datetime
from app import create_app
from app.models.surrogate_task import SurrogateTask

def analyze_collection_tasks():
    app = create_app()
    with app.app_context():
        # Find all collect tasks that are succeeded
        tasks = SurrogateTask.query.filter_by(type='collect', status='succeeded').order_by(SurrogateTask.created_at.desc()).all()
        
        print(f"Found {len(tasks)} succeeded collect tasks.")
        
        for t in tasks:
            print(f"\nTask ID: {t.id}, Name: {t.name}, Created: {t.created_at}")
            if t.training_params:
                try:
                    params = json.loads(t.training_params)
                    metrics = params.get('collection_metrics', [])
                    if metrics:
                        start = metrics[0]
                        end = metrics[-1]
                        
                        start_time = datetime.datetime.fromisoformat(start['time'])
                        end_time = datetime.datetime.fromisoformat(end['time'])
                        duration = (end_time - start_time).total_seconds()
                        
                        start_samples = start.get('samples', 0)
                        end_samples = end.get('samples', 0)
                        total_samples = end_samples - start_samples
                        if total_samples == 0 and len(metrics) > 1:
                             # Maybe start was 0 and end is total
                             total_samples = end_samples
                        
                        print(f"  Duration: {duration:.2f}s ({duration/60:.2f} min)")
                        print(f"  Samples: {total_samples}")
                        if total_samples > 0:
                            rate = duration / total_samples
                            print(f"  Rate: {rate:.4f} seconds/sample")
                            print(f"  Throughput: {total_samples/duration:.4f} samples/second")
                        
                        print(f"  Devices: {end.get('devices', 1)}")
                    else:
                        print("  No collection_metrics found.")
                        
                        # Fallback: check created_at vs updated_at
                        if t.updated_at and t.created_at:
                            duration = (t.updated_at - t.created_at).total_seconds()
                            print(f"  (Est from DB) Duration: {duration:.2f}s")
                            
                except Exception as e:
                    print(f"  Error parsing params: {e}")
            else:
                print("  No training_params.")

if __name__ == "__main__":
    analyze_collection_tasks()
