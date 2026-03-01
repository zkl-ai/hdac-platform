import sys
import os
from app import create_app
from app.extensions import db
from app.models.compress_task import CompressTask, CompressStage

app = create_app()

with app.app_context():
    # Delete all stages first due to foreign key constraint
    deleted_stages = CompressStage.query.delete()
    deleted_tasks = CompressTask.query.delete()
    db.session.commit()
    print(f"Deleted {deleted_tasks} tasks and {deleted_stages} stages.")
