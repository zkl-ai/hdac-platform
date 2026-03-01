
from app import create_app
from app.models.surrogate_pipeline import SurrogatePipeline
from sqlalchemy import or_
from app.extensions import db

app = create_app()
with app.app_context():
    pid = 219
    print(f"Testing lookup for ID: {pid}")
    
    # Test 1: Direct ID
    p1 = SurrogatePipeline.query.get(pid)
    print(f"Direct Get: {p1}")
    
    # Test 2: Filter
    p2 = SurrogatePipeline.query.filter(
        or_(
            SurrogatePipeline.cluster_task_id == pid,
            SurrogatePipeline.collect_task_id == pid,
            SurrogatePipeline.train_task_id == pid
        )
    ).first()
    print(f"Filter Result: {p2}")
    if p2:
        print(f"  Found Pipeline: {p2.id} (Train Task ID: {p2.train_task_id})")
        
    # Test 3: Raw SQL to verify
    sql = SurrogatePipeline.query.filter(
        or_(
            SurrogatePipeline.cluster_task_id == pid,
            SurrogatePipeline.collect_task_id == pid,
            SurrogatePipeline.train_task_id == pid
        )
    ).statement
    print(f"Generated SQL: {sql}")

