from datetime import datetime
from app.extensions import db

class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    display_name = db.Column(db.String(128))
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 角色下有哪些权限
    permissions = db.relationship(
        'Permission',
        secondary='role_permissions',
        back_populates='roles'
    )

    # 角色下有哪些用户
    users = db.relationship(
        'User',
        secondary='user_roles',
        back_populates='roles'
    )
