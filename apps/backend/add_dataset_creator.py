
import os
import sys
from sqlalchemy import text, inspect

# Add current directory to path so we can import app
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('datasets')]
    
    if 'created_by' in columns:
        print("'created_by' column already exists.")
    else:
        print("'created_by' column does not exist. Adding it...")
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE datasets ADD COLUMN created_by VARCHAR(64) DEFAULT 'admin'"))
            print("Added 'created_by' column.")
        except Exception as e:
            print(f"Failed to add column created_by: {e}")
            sys.exit(1)
            
    print("Done!")
