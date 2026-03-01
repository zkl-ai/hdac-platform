from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field

T = TypeVar("T")

# 基础外层格式
class BaseResp(BaseModel):
    code: int = Field(0, description="状态码，0=成功")
    message: str = Field("ok", description="提示信息")

# 泛型外层，data 可以是任意模型
class Resp(BaseResp, Generic[T]):
    data: Optional[T] = Field(default=None, description="业务数据")

# 常见内层示例
class TokenUser(BaseModel):
    token: str
    user: dict  # 这里可再细化为 UserOut 模型