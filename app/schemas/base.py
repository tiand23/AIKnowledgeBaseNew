"""
统一响应模型基类
"""
from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar

T = TypeVar('T')


class BaseResponse(BaseModel, Generic[T]):
    """
    统一响应格式基类
    
    所有API响应都应该继承此类，确保返回格式统一：
    {
        "code": 200,
        "message": "操作成功",
        "data": {...}
    }
    
    使用示例:
        class UserData(BaseModel):
            id: int
            name: str
        
        class UserResponse(BaseResponse[UserData]):
            code: int = Field(200, description="状态码")
            message: str = Field("获取用户成功", description="提示信息")
    """
    code: int = Field(200, description="状态码")
    message: str = Field("Success", description="提示信息")
    data: Optional[T] = Field(None, description="数据")


class ErrorResponse(BaseModel):
    """
    统一错误响应格式
    
    用于错误响应，确保错误格式统一：
    {
        "code": 400,
        "message": "错误信息",
        "data": {...}  # Optional error details
    }
    """
    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误信息")
    data: Optional[dict] = Field(None, description="错误详情")
