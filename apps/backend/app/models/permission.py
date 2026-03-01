from datetime import datetime
from app.extensions import db


# ======================
#  Permissions 表
# ======================
class Permission(db.Model):
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    display_name = db.Column(db.String(128))
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 反向关联：roles = [Role, Role...]
    roles = db.relationship('Role', secondary='role_permissions', back_populates='permissions')

