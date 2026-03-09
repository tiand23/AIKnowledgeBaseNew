"""
检索相关 Schema
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.schemas.base import BaseResponse


class HybridSearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询字符串", min_length=1, max_length=500)
    topK: int = Field(default=10, description="返回结果数量", ge=1, le=100)


class SearchResultItem(BaseModel):
    file_md5: str = Field(..., description="文件MD5指纹")
    chunk_id: int = Field(..., description="文本分块序号")
    text_content: str = Field(..., description="原始文本内容")
    score: float = Field(..., description="相关性分数")
    file_name: str = Field(..., description="文件名")


class HybridSearchResponse(BaseResponse[List[SearchResultItem]]):
    code: int = Field(200, description="状态码")
    message: str = Field("检索成功", description="提示信息")


class ScheduleDebugItem(BaseModel):
    file_md5: str = Field(..., description="文件MD5")
    file_name: str = Field(..., description="文件名")
    sheet: Optional[str] = Field(None, description="sheet名称")
    row_no: Optional[int] = Field(None, description="Excel行号")
    task: Optional[str] = Field(None, description="任务名")
    period_start: Optional[str] = Field(None, description="开始标签")
    period_end: Optional[str] = Field(None, description="结束标签")
    task_detail: Optional[str] = Field(None, description="任务说明")
    confidence: float = Field(0.0, description="解析置信度")
    match_score: float = Field(0.0, description="与查询的匹配分数")


class ScheduleDebugResponse(BaseResponse[List[ScheduleDebugItem]]):
    code: int = Field(200, description="状态码")
    message: str = Field("调试数据获取成功", description="提示信息")


class DocumentDeleteResponse(BaseResponse[Optional[Dict[str, Any]]]):
    code: int = Field(200, description="状态码")
    message: str = Field("文档删除成功", description="提示信息")
