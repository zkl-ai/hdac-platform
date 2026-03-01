
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models.gray_deploy_task import GrayDeployTask

def rename_task():
    app = create_app()
    with app.app_context():
        # Find the task
        old_name = "CanaryDeploy-ResNet-Tiny-56-CIFAR10-20260225"
        new_name = "GrayDeploy-ResNet-Tiny-56-CIFAR10-20260225"
        
        task = GrayDeployTask.query.filter_by(name=old_name).first()
        
        if task:
            print(f"Found task: {task.name} (ID: {task.id})")
            task.name = new_name
            db.session.commit()
            print(f"Successfully renamed to: {task.name}")
        else:
            print(f"Task with name '{old_name}' not found.")
            # Let's list all tasks to see what we have, maybe the date is different
            print("Listing all GrayDeployTasks:")
            tasks = GrayDeployTask.query.all()
            for t in tasks:
                print(f" - ID: {t.id}, Name: {t.name}")

if __name__ == "__main__":
    rename_task()
