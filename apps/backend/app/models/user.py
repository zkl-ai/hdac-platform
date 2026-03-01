from datetime import datetime
from app.extensions import db
from app.utils.security import verify_password 


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(128))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 注意：你的表里 primary_role 是 VARCHAR，不是外键
    primary_role = db.Column(db.String(64))

    # 一个用户可以有多个角色
    roles = db.relationship(
        'Role',
        secondary='user_roles',
        back_populates='users'
    )

    def check_password(self, password: str) -> bool:
        """
        验证密码，使用 app.utils.security.verify_password。
        返回 True 表示密码正确。
        """
        if not self.password_hash:
            return False
        return verify_password(password, self.password_hash)

