from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.utils.response import success, fail
from app.models import User
from app.schemas.orm import UserOut


user_bp = Blueprint('user', __name__, url_prefix='/api')  

@user_bp.get('/user/info')
@jwt_required()
def user_info():
    user = User.query.get(get_jwt_identity())
    if not user:
        return fail(message='用户不存在', code=404)
    data = UserOut.from_orm(user).model_dump(by_alias=True)
    return success(data=data)