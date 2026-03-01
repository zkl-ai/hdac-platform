from app.extensions import db

class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), unique=True, nullable=False)
    username = db.Column(db.String(128), nullable=True)
    password = db.Column(db.String(256), nullable=True)
    port = db.Column(db.Integer, default=22)
    type = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(32), default='offline')
    removed = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'ip': self.ip,
            'username': self.username,
            'port': self.port,
            'type': self.type,
            'status': self.status,
            'removed': self.removed,
        }
