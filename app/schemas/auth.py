"""
认证相关的 Pydantic 模型（已与当前 User 模型对齐）
"""
from pydantic import BaseModel, EmailStr, Field, constr
from datetime import datetime
from typing import Optional, Literal, List
from app.schemas.base import BaseResponse


class CaptchaData(BaseModel):
    captcha_id: str = Field(..., description="验证码ID")
    captcha_image: str = Field(..., description="Base64编码的图片")


class CaptchaResponse(BaseResponse[CaptchaData]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取验证码成功", description="提示信息")


class UserRegisterRequest(BaseModel):
    username: constr(min_length=3, max_length=50) = Field(..., description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: constr(min_length=6, max_length=50) = Field(..., description="密码")
    org_tags: List[str] = Field(default_factory=list, description="注册时选择的组织标签")
    primary_org: Optional[str] = Field(None, description="主组织标签")


class UserRegisterData(BaseModel):
    id: int
    username: str
    email: EmailStr
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer")


class UserRegisterResponse(BaseResponse[UserRegisterData]):
    code: int = Field(200, description="状态码")
    message: str = Field("注册成功", description="提示信息")


class RegisterOrgTagOption(BaseModel):
    tagId: str
    name: str
    description: Optional[str] = None


class RegisterOrgTagOptionsResponse(BaseResponse[List[RegisterOrgTagOption]]):
    code: int = Field(200, description="状态码")
    message: str = Field("注册组织标签列表获取成功", description="提示信息")


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str


class UserLoginData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    email: EmailStr


class UserLoginResponse(BaseResponse[UserLoginData]):
    code: int = Field(200, description="状态码")
    message: str = Field("登录成功", description="提示信息")


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: Literal["USER", "ADMIN"]
    org_tags: Optional[str] = None
    primary_org: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserInfoData(BaseModel):
    id: int
    username: str
    role: str
    orgTags: List[str]
    primaryOrg: Optional[str] = None


class UserInfoResponse(BaseResponse[UserInfoData]):
    code: int = Field(200, description="状态码")
    message: str = Field("Success", description="提示信息")


class UserListItem(BaseModel):
    userId: int
    username: str
    email: str
    orgTags: List[str]
    primaryOrg: Optional[str] = None
    createTime: datetime


class UserListContent(BaseModel):
    content: List[UserListItem]
    totalElements: int
    totalPages: int
    size: int
    number: int


class UserListResponse(BaseResponse[UserListContent]):
    code: int = Field(200, description="状态码")
    message: str = Field("Get users successful", description="提示信息")
