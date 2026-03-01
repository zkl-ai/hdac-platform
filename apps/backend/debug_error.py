from app import create_app
from app.models.surrogate_task import SurrogateTask
import json

app = create_app()
with app.app_context():
    # Find the most recent failed cluster task
    task = SurrogateTask.query.filter_by(type='cluster', status='failed').order_by(SurrogateTask.created_at.desc()).first()
    if task:
        print(f"Task ID: {task.id}")
        print(f"Status: {task.status}")
        if task.training_params:
            try:
                p = json.loads(task.training_params)
                print(f"Errors: {p.get('errors')}")
            except:
                print("Could not parse params")
    else:
        print("No failed cluster task found.")
