
import sys
import os
from sqlalchemy import text

# Add current directory to path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db

def update_schema():
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(text("SELECT device_subset FROM gray_deploy_tasks LIMIT 1"))
            print("Column 'device_subset' already exists in gray_deploy_tasks.")
        except Exception:
            print("Adding 'device_subset' to gray_deploy_tasks...")
            try:
                db.session.execute(text("ALTER TABLE gray_deploy_tasks ADD COLUMN device_subset TEXT"))
                print("Added 'device_subset' to gray_deploy_tasks.")
            except Exception as e:
                print(f"Error adding column: {e}")
                
        db.session.commit()

if __name__ == "__main__":
    update_schema()
