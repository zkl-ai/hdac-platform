from datetime import datetime
from app.extensions import db


class SurrogateTask(db.Model):
    __tablename__ = 'surrogate_tasks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    type = db.Column(db.String(32), nullable=False)
    dnn_model_name = db.Column(db.String(128))
    surrogate_structure = db.Column(db.String(256))
    device_list = db.Column(db.String(512))
    dataset_size = db.Column(db.Integer)
    training_params = db.Column(db.Text)
    mape = db.Column(db.Float)
    accel_effect = db.Column(db.String(64))
    status = db.Column(db.String(32), default='pending')
    progress = db.Column(db.Integer, default=0)
    created_by = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'dnnModelName': self.dnn_model_name,
            'surrogateStructure': self.surrogate_structure,
            'deviceList': self.device_list,
            'datasetSize': self.dataset_size,
            'trainingParams': self.training_params,
            'mape': self.mape,
            'accelEffect': self.accel_effect,
            'status': self.status,
            'progress': self.progress,
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
