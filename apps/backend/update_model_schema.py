
from app import create_app
from app.extensions import db
from sqlalchemy import text

def add_created_by_column():
    app = create_app()
    with app.app_context():
        print("Adding created_by column to models table...")
        try:
            # Check if column exists first to avoid error
            # This is DB specific, for SQLite/MySQL/Postgres
            # Assuming MySQL based on previous context
            
            # Try to select the column, if fails, add it
            try:
                db.session.execute(text("SELECT created_by FROM models LIMIT 1"))
                print("Column 'created_by' already exists.")
            except Exception:
                print("Column 'created_by' does not exist. Adding it...")
                # We need to rollback the failed transaction first if using Postgres, 
                # but for MySQL usually it's fine or we need rollback.
                db.session.rollback()
                
                db.session.execute(text("ALTER TABLE models ADD COLUMN created_by VARCHAR(64) DEFAULT 'alice_admin'"))
                db.session.commit()
                print("Column added.")
                
            # Update all existing records
            print("Updating existing records to 'alice_admin'...")
            db.session.execute(text("UPDATE models SET created_by = 'alice_admin' WHERE created_by IS NULL"))
            db.session.commit()
            print("Done.")
            
        except Exception as e:
            print(f"Error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    add_created_by_column()
