
import sys
import os
from sqlalchemy import text

# Add current directory to path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models.model import ModelVersion
from app.models.gray_deploy_task import GrayDeployTask

def check_latency():
    app = create_app()
    with app.app_context():
        # Find the task
        task_name = "GrayDeploy-ResNet-Tiny-56-CIFAR10-20260226" # Or similar ID 36
        task = GrayDeployTask.query.get(36)
        
        if not task:
            print("Task 36 not found")
            return

        print(f"Task: {task.name}, Version ID: {task.version_id}")
        
        if task.version_id:
            v = ModelVersion.query.get(task.version_id)
            if v:
                print(f"Model Version: {v.name}")
                print(f"Stored avg_latency_ms: {v.avg_latency_ms}")
            else:
                print("Version not found")
        else:
            print("No version ID linked")

if __name__ == "__main__":
    check_latency()
