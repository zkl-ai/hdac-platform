from flask import Blueprint, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.models import User
from app.schemas.auth import LoginSchemaIn
from app.schemas.orm import UserOut
from app.services.auth_service import AuthService
from app.utils.response import fail, success

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


# ---------- 登录 ----------
@auth_bp.post("/auth/login")
def login():
    try:
        body = LoginSchemaIn(**request.json)
    except ValidationError as e:
        return fail(message="参数格式错误", data=e.errors(), code=400, http_status=400)

    user, error = AuthService.authenticate(body.username, body.password)
    if error:
        return fail(message=error, code=401, http_status=401)

    access_token = create_access_token(identity=user.id)
    user_out = UserOut.from_orm(user).model_dump(by_alias=True)
    return success(data={"accessToken": access_token, "user": user_out})


# ---------- 登出 (可选，JWT通常客户端删除即可) ----------
@auth_bp.post("/auth/logout")
def logout():
    # Since we are not using a blacklist, we just return success
    # The client should discard the token
    return success(message="已登出")


# ---------- 权限码 ----------
@auth_bp.get("/auth/codes")
@jwt_required()
def auth_codes():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user is None:
        return fail(message="用户不存在", code=404)

    codes = {p.name for r in user.roles for p in r.permissions}
    return success(data=sorted(codes))