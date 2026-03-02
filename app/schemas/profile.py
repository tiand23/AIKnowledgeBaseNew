"""
知识库场景配置 Schema
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class ProfileOption(BaseModel):
    profile_id: str = Field(..., description="场景ID")
    name: str = Field(..., description="场景名称")
    description: str = Field(..., description="场景说明")


class ProfileStateData(BaseModel):
    selected_profile: Optional[str] = Field(None, description="当前已选场景ID")
    selected_name: Optional[str] = Field(None, description="当前已选场景名称")
    locked: bool = Field(False, description="是否已锁定")
    options: List[ProfileOption] = Field(default_factory=list, description="可选场景列表")


class ProfileStateResponse(BaseResponse[ProfileStateData]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取场景配置成功", description="提示信息")


class ProfileSelectRequest(BaseModel):
    profile_id: str = Field(..., description="要选择的场景ID")


class ProfileSelectResponse(BaseResponse[ProfileStateData]):
    code: int = Field(200, description="状态码")
    message: str = Field("场景配置已保存", description="提示信息")


class IntentKeywordCategory(BaseModel):
    key: str = Field(..., description="关键词分类键")
    label: str = Field(..., description="分类名称")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")


class IntentKeywordsConfigData(BaseModel):
    categories: List[IntentKeywordCategory] = Field(default_factory=list, description="关键词配置")
    updated_at: Optional[datetime] = Field(None, description="最后更新时间")


class IntentKeywordsConfigResponse(BaseResponse[IntentKeywordsConfigData]):
    code: int = Field(200, description="状态码")
    message: str = Field("意图关键词配置获取成功", description="提示信息")


class IntentKeywordCategoryUpdate(BaseModel):
    key: str = Field(..., description="关键词分类键")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")


class IntentKeywordsUpdateRequest(BaseModel):
    categories: List[IntentKeywordCategoryUpdate] = Field(default_factory=list, description="要更新的关键词分类")


class IntentKeywordsUpdateResponse(BaseResponse[IntentKeywordsConfigData]):
    code: int = Field(200, description="状态码")
    message: str = Field("意图关键词配置已保存", description="提示信息")
