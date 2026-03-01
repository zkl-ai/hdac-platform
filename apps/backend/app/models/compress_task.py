from datetime import datetime
from app.extensions import db


class CompressTask(db.Model):
    __tablename__ = 'compress_tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    model_name = db.Column(db.String(128), nullable=False)
    device_type = db.Column(db.String(128))
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
            'status': self.status,
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }


class CompressStage(db.Model):
    __tablename__ = 'compress_stages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('compress_tasks.id', ondelete='CASCADE'), nullable=False)
    phase = db.Column(db.String(32), nullable=False)  # pruning / finetune
    status = db.Column(db.String(32), default='pending')
    progress = db.Column(db.Integer, default=0)
    compression_algo = db.Column(db.String(128))
    algo_params = db.Column(db.Text)
    eval_metric = db.Column(db.String(128))
    latency_budget = db.Column(db.Float)
    accuracy_loss_limit = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'taskId': self.task_id,
            'phase': self.phase,
            'status': self.status,
            'progress': self.progress,
            'compressionAlgo': self.compression_algo,
            'algoParams': self.algo_params,
            'evalMetric': self.eval_metric,
            'latencyBudget': self.latency_budget,
            'accuracyLossLimit': self.accuracy_loss_limit,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }

