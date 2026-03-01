from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

# ---------- 入参 ----------
class LoginSchemaIn(BaseModel):
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")
    
    
