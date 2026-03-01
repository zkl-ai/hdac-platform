from datetime import datetime
from app.extensions import db


class GrayDeployTask(db.Model):
    __tablename__ = 'gray_deploy_tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    model_name = db.Column(db.String(128), nullable=False)
    version_id = db.Column(db.Integer) # Linked to ModelVersion.id
    device_type = db.Column(db.String(128))
    device_subset = db.Column(db.Text) # Comma-separated list of device IDs or IPs
    status = db.Column(db.String(32), default='pending')
    created_by = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'modelName': self.model_name,
            'deviceType': self.device_type,
            'deviceSubset': self.device_subset,
            'status': self.status,
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }


class GrayDeployStage(db.Model):
    __tablename__ = 'gray_deploy_stages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('gray_deploy_tasks.id', ondelete='CASCADE'), nullable=False)
    phase = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(32), default='pending')
    progress = db.Column(db.Integer, default=0)
    gray_ratio = db.Column(db.Float)
    latency_ms = db.Column(db.Float)
    accuracy = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'taskId': self.task_id,
            'phase': self.phase,
            'status': self.status,
            'progress': self.progress,
            'grayRatio': self.gray_ratio,
            'latencyMs': self.latency_ms,
            'accuracy': self.accuracy,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }


class GrayInferenceRecord(db.Model):
    __tablename__ = 'gray_inference_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('gray_deploy_tasks.id', ondelete='CASCADE'), nullable=False)
    is_candidate = db.Column(db.Boolean, default=False)
    latency_ms = db.Column(db.Float)
    http_status = db.Column(db.Integer, default=200)
    device_id = db.Column(db.String(64)) # Optional: record which device handled the request
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'taskId': self.task_id,
            'isCandidate': self.is_candidate,
            'latencyMs': self.latency_ms,
            'httpStatus': self.http_status,
            'deviceId': self.device_id,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
        }


class GraySystemMetric(db.Model):
    __tablename__ = 'gray_system_metrics'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('gray_deploy_tasks.id', ondelete='CASCADE'), nullable=False)
    device_id = db.Column(db.String(64)) # Optional: which device reported this
    cpu_percent = db.Column(db.Float)
    memory_percent = db.Column(db.Float)
    gpu_percent = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'taskId': self.task_id,
            'deviceId': self.device_id,
            'cpuPercent': self.cpu_percent,
            'memoryPercent': self.memory_percent,
            'gpuPercent': self.gpu_percent,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
        }
