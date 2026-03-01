# app/schemas/orm.py
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

# ========== Permission ==========
class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    permId: int = Field(alias="id")
    name: str
    displayName: str = Field(alias="display_name")
    description: Optional[str] = None


# ========== Role ==========
class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    roleId: int = Field(alias="id")
    name: str
    displayName: str = Field(alias="display_name")
    description: Optional[str] = None
    permissions: List[PermissionOut] = []  # 嵌套权限列表

    @classmethod
    def from_orm(cls, role):
        """把 ORM 对象列表一次性转干净"""
        return cls.model_validate(
            {
                **role.__dict__,
                "permissions": [PermissionOut.model_validate(p) for p in role.permissions],
            }
        )


# ========== User ==========
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, by_alias=True)

    userId: int = Field(alias="id")
    username: str
    realName: str = Field(alias="username")  # 先用 username 顶
    email: Optional[str] = None
    isActive: bool = Field(alias="is_active")
    primaryRole: Optional[str] = Field(None, alias="primary_role")
    roles: List[RoleOut] = []  # 嵌套角色+权限
    homePath: str = Field('/dashboard')

    @classmethod
    def from_orm(cls, user):
        return cls.model_validate(
            {
                **user.__dict__,
                "roles": [RoleOut.from_orm(r) for r in user.roles],
            }
        )