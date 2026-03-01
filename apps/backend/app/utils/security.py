import bcrypt

def hash_password(password: str) -> str:
    """
    使用 bcrypt 生成密码哈希，返回 str（可直接写入 DB）。
    Example:
        >>> hash_password("Admin123!")
        "$2b$12$...."
    """
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    # bcrypt.hashpw 返回 bytes，decode 成 str 存数据库
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    使用 bcrypt 校验密码。返回 True/False。
    注意：password_hash 必须是 bcrypt.hashpw 生成的字符串（例如以 $2b$ 开头）。
    """
    try:
        # bcrypt.checkpw 要求 bytes
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False
