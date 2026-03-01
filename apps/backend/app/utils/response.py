from flask import jsonify, current_app
from app.schemas.response import Resp

# -------------- 手动调用 --------------
def success(data=None, message: str = "ok", code: int = 0):
    """返回成功格式，data 可以是任意 Pydantic 模型或 dict"""
    
    return Resp(code=code, message=message, data=data).model_dump(exclude_none=True), 200

def fail(message: str = "error", code: int = 1, http_status: int = 400):
    return Resp(code=code, message=message, data={}).model_dump(), http_status

# -------------- 全局自动包 --------------
def init_response_handler(app):
    """注册后，所有正常 JSON 响应自动包成 Resp"""
    from app.schemas.response import Resp

    @app.after_request
    def uniform(resp):
        if resp.content_type != "application/json" or resp.status_code >= 400:
            return resp  # 只处理 2xx JSON
        original = resp.get_json()
        if isinstance(original, dict) and "code" in original:
            return resp  # 已经包过
        wrapped = Resp(data=original).dict(exclude_none=True)
        return jsonify(wrapped), resp.status_code