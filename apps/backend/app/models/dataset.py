from datetime import datetime
from app.extensions import db

class Dataset(db.Model):
    __tablename__ = 'datasets'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    path = db.Column(db.String(512), nullable=False)
    type = db.Column(db.String(32), default='Image Classification') # e.g. Image Classification, Object Detection
    size = db.Column(db.String(64), default='N/A')
    size_bytes = db.Column(db.BigInteger, default=0)
    created_by = db.Column(db.String(64), default='admin')
    description = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'type': self.type,
            'size': self.size,
            'sizeBytes': self.size_bytes,
            'createdBy': self.created_by,
            'description': self.description,
            'createdAt': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
