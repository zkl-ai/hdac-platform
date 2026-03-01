from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.dataset import Dataset
from app.models.model import ModelVersion
from app.models.user import User
from app.utils.response import success, fail

dataset_bp = Blueprint('dataset', __name__, url_prefix='/api')

import os
import subprocess

def get_dir_size(path):
    try:
        if not os.path.exists(path):
            return "N/A"
        # Use du -sh for accurate disk usage
        # -s: summary, -h: human readable (though we might want raw bytes to format consistently, 
        # but user liked du -sh output. Let's return raw bytes to format consistently in our format_size function
        # or just grab the string if we trust du's format. 
        # User output: 148G. format_size produces 148.00 GB. 
        # Let's use `du -sb` to get bytes and use our formatter for consistency.
        # Wait, user explicitly compared with `du -sh`. 
        # Let's use `du -sb` (bytes) and pass to format_size to ensure we match the magnitude.
        
        # However, `du -sb` counts apparent size, `du -s` counts disk usage (blocks). 
        # `du -sh` uses block counts. `du -sb` uses apparent size.
        # User showed `du -sh` 148G. 
        # If I use `du -s` (blocks in 1k) * 1024, I get bytes.
        
        output = subprocess.check_output(['du', '-s', path], timeout=3).decode('utf-8')
        # Output format: "155234234\t/path/to/dir"
        kb_size = int(output.split()[0])
        total_bytes = kb_size * 1024
        return format_size(total_bytes)
    except Exception:
        return "N/A"

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

@dataset_bp.get('/datasets')
def list_datasets():
    try:
        q = Dataset.query.order_by(Dataset.created_at.desc())
        datasets = q.all()
        
        # Optimize linked models count (N+1 problem)
        from sqlalchemy import func
        counts = db.session.query(ModelVersion.dataset, func.count(ModelVersion.id)).group_by(ModelVersion.dataset).all()
        count_map = {c[0]: c[1] for c in counts} # { 'CIFAR-10': 5, ... }

        items = []
        total_bytes = 0
        
        for d in datasets:
            d_dict = d.to_dict()
            # Count linked models using map
            d_dict['linkedModels'] = count_map.get(d.name, 0)
            
            # Sum total size
            if d.size_bytes:
                total_bytes += d.size_bytes
                
            items.append(d_dict)
            
        total_size_str = format_size(total_bytes)
        
        return success(data={
            'items': items,
            'totalSize': total_size_str,
            'totalSizeBytes': total_bytes
        })
    except Exception as e:
        return fail(message=str(e))

@dataset_bp.post('/datasets')
@jwt_required()
def create_dataset():
    try:
        body = request.json or {}
        name = (body.get('name') or '').strip()
        path = (body.get('path') or '').strip()
        type_ = (body.get('type') or '').strip()
        desc = (body.get('description') or '').strip()

        # Get current user
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        created_by = user.username if user else 'admin'

        if not name or not path:
            return fail(message='Name and Path are required', code=400, http_status=400)

        if Dataset.query.filter_by(name=name).first():
            return fail(message='Dataset name already exists', code=400, http_status=400)

        # Calculate size immediately
        size_str = "N/A"
        size_bytes = 0
        try:
            if os.path.exists(path):
                output = subprocess.check_output(['du', '-s', path], timeout=3).decode('utf-8')
                kb_size = int(output.split()[0])
                size_bytes = kb_size * 1024
                size_str = format_size(size_bytes)
        except Exception:
            pass

        d = Dataset(
            name=name, 
            path=path, 
            type=type_, 
            description=desc, 
            size=size_str, 
            size_bytes=size_bytes,
            created_by=created_by
        )
        db.session.add(d)
        db.session.commit()
        return success(message='Dataset created', data=d.to_dict())
    except Exception as e:
        db.session.rollback()
        return fail(message=str(e))

@dataset_bp.delete('/datasets/<int:id>')
def delete_dataset(id):
    try:
        d = Dataset.query.get(id)
        if not d:
            return fail(message='Dataset not found', code=404, http_status=404)
        db.session.delete(d)
        db.session.commit()
        return success(message='Dataset deleted')
    except Exception as e:
        db.session.rollback()
        return fail(message=str(e))
