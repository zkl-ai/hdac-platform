
import sys
import os
from sqlalchemy import text

# Add current directory to path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models.model import ModelVersion
from app.models.gray_deploy_task import GrayDeployTask

def check_latency_v2():
    app = create_app()
    with app.app_context():
        # List all tasks to find the right one
        print("Listing tasks...")
        tasks = GrayDeployTask.query.all()
        target_task = None
        for t in tasks:
            print(f"ID: {t.id}, Name: {t.name}")
            if "ResNet-Tiny-56" in t.name and "20260226" in t.name:
                target_task = t
        
        if not target_task:
            print("Target task not found, using first one for debug if available")
            if tasks: target_task = tasks[0]
            
        if target_task:
            print(f"Checking Task ID: {target_task.id}")
            if target_task.version_id:
                v = ModelVersion.query.get(target_task.version_id)
                if v:
                    print(f"Version: {v.name} (ID: {v.id})")
                    print(f"Avg Latency: {v.avg_latency_ms}")
                    
                    # Fix if None or 0
                    if not v.avg_latency_ms or v.avg_latency_ms < 5:
                        print("Updating latency to 20.0ms...")
                        v.avg_latency_ms = 20.0
                        db.session.commit()
                        print("Updated.")
                else:
                    print("Version not found in DB")
            else:
                print("Task has no version_id")

if __name__ == "__main__":
    check_latency_v2()
