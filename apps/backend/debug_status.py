from app import create_app
from app.models.surrogate_task import SurrogateTask
import json

app = create_app()
with app.app_context():
    # Find the most recent tasks
    print("--- Recent Tasks ---")
    tasks = SurrogateTask.query.order_by(SurrogateTask.created_at.desc()).limit(3).all()
    for t in tasks:
        print(f"ID: {t.id} | Name: {t.name} | Type: {t.type} | Status: {t.status}")
        
    print("\n--- Cluster Results (Latest Completed) ---")
    cluster_task = SurrogateTask.query.filter_by(type='cluster', status='succeeded').order_by(SurrogateTask.created_at.desc()).first()
    if cluster_task:
        print(f"Cluster Task ID: {cluster_task.id}")
        if cluster_task.training_params:
             try:
                 params = json.loads(cluster_task.training_params)
                 print("Clusters:")
                 print(json.dumps(params.get('clusters'), indent=2))
                 print("Cluster Mapping:")
                 print(json.dumps(params.get('cluster_mapping'), indent=2))
             except Exception as e:
                 print(f"Error parsing training_params: {e}")
        else:
             print("No training_params set.")
    else:
        print("No succeeded cluster task found.")
        
    print("\n--- Collect Task Status (Latest Failed) ---")
    collect_task = SurrogateTask.query.filter_by(type='collect', status='failed').order_by(SurrogateTask.created_at.desc()).first()
    if collect_task:
         print(f"Collect Task ID: {collect_task.id}")
         print(f"Status: {collect_task.status}")
         if collect_task.training_params:
             try:
                 params = json.loads(collect_task.training_params)
                 print("Errors:")
                 print(json.dumps(params.get('errors'), indent=2))
             except Exception as e:
                 print(f"Error parsing params: {e}")
    else:
         print("No failed collect task found.")
