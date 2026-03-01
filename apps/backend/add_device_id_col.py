
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
        # Check if column exists
        try:
            db.session.execute(text("SELECT device_id FROM gray_inference_records LIMIT 1"))
            print("Column 'device_id' already exists in gray_inference_records.")
        except Exception:
            print("Adding 'device_id' to gray_inference_records...")
            try:
                db.session.execute(text("ALTER TABLE gray_inference_records ADD COLUMN device_id VARCHAR(64)"))
                print("Added 'device_id' to gray_inference_records.")
            except Exception as e:
                print(f"Error adding column: {e}")

        try:
            db.session.execute(text("SELECT device_id FROM gray_system_metrics LIMIT 1"))
            print("Column 'device_id' already exists in gray_system_metrics.")
        except Exception:
            print("Adding 'device_id' to gray_system_metrics...")
            try:
                db.session.execute(text("ALTER TABLE gray_system_metrics ADD COLUMN device_id VARCHAR(64)"))
                print("Added 'device_id' to gray_system_metrics.")
            except Exception as e:
                print(f"Error adding column: {e}")
                
        db.session.commit()

if __name__ == "__main__":
    update_schema()
