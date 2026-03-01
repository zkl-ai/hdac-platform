from datetime import datetime
from app.extensions import db


class Model(db.Model):
    __tablename__ = 'models'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)  # ResNet50 / VGG19 / MobileNetV1 / YOLOv8n
    type = db.Column(db.String(32), nullable=False)   # DNN / Surrogate
    
    # Metadata
    task_type = db.Column(db.String(64), default='Image Classification')
    input_dim = db.Column(db.String(64)) # e.g. 1x3x224x224
    output_dim = db.Column(db.String(64)) # e.g. 1000
    model_flops = db.Column(db.Float) # GFLOPs
    
    created_by = db.Column(db.String(64), default='alice_admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ModelVersion(db.Model):
    __tablename__ = 'model_versions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    model_id = db.Column(db.Integer, db.ForeignKey('models.id', ondelete='CASCADE'), nullable=False)
    device_type = db.Column(db.String(128), nullable=False)  # Jetson Nano / Jetson Xavier / STM32H7
    
    name = db.Column(db.String(128), nullable=False) # e.g. "v1", "proxy-v1", "uncompressed"
    type = db.Column(db.String(32), nullable=False) # DNN / Surrogate
    
    file_path = db.Column(db.String(512)) # Weights path (.pth)
    definition_path = db.Column(db.String(512)) # Model definition (.py)
    profiler_path = db.Column(db.String(512)) # Profiling script (.py)
    
    # Dataset info
    dataset = db.Column(db.String(128))  # ImageNet / COCO
    accuracy = db.Column(db.String(64))  # Top-1 76.2% / mAP 37.2
    
    # Performance metrics
    flops = db.Column(db.Float)
    avg_latency_ms = db.Column(db.Float)
    compressed = db.Column(db.Boolean, default=False)
    time = db.Column(db.String(32))
    source_task_id = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
