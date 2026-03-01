from datetime import datetime
from app.extensions import db


class SurrogatePipeline(db.Model):
    __tablename__ = 'surrogate_pipelines'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    model_name = db.Column(db.String(128), nullable=False)
    device_type = db.Column(db.String(128), nullable=False)
    dataset_name = db.Column(db.String(128))
    cluster_task_id = db.Column(db.Integer)
    collect_task_id = db.Column(db.Integer)
    train_task_id = db.Column(db.Integer)
    status = db.Column(db.String(32), default='pending')
    progress = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'modelName': self.model_name,
            'deviceType': self.device_type,
            'datasetName': self.dataset_name,
            'clusterTaskId': self.cluster_task_id,
            'collectTaskId': self.collect_task_id,
            'trainTaskId': self.train_task_id,
            'status': self.status,
            'progress': self.progress,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
