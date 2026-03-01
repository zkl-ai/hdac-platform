
import os
import sys
import subprocess
from sqlalchemy import text, inspect

# Add current directory to path so we can import app
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models.dataset import Dataset

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def get_dir_size(path):
    try:
        if not os.path.exists(path):
            return "N/A", 0
        output = subprocess.check_output(['du', '-s', path], timeout=3).decode('utf-8')
        kb_size = int(output.split()[0])
        total_bytes = kb_size * 1024
        return format_size(total_bytes), total_bytes
    except Exception as e:
        print(f"Error calculating size for {path}: {e}")
        return "N/A", 0

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('datasets')]
    
    if 'size_bytes' in columns:
        print("'size_bytes' column already exists.")
    else:
        print("'size_bytes' column does not exist. Adding it...")
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE datasets ADD COLUMN size_bytes BIGINT DEFAULT 0"))
                # conn.commit()
            print("Added 'size_bytes' column.")
        except Exception as e:
            print(f"Failed to add column size_bytes: {e}")
            sys.exit(1)

    print("Updating dataset sizes...")
    try:
        datasets = Dataset.query.all()
        for d in datasets:
            print(f"Processing dataset: {d.name} ({d.path})")
            new_size_str, new_size_bytes = get_dir_size(d.path)
            print(f"  -> Size: {new_size_str} ({new_size_bytes} bytes)")
            d.size = new_size_str
            d.size_bytes = new_size_bytes
        
        db.session.commit()
        print("Done!")
    except Exception as e:
        db.session.rollback()
        print(f"Error updating datasets: {e}")
