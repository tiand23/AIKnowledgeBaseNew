"""
聊天相关 Schema
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.base import BaseResponse


class MessageItem(BaseModel):
    role: str = Field(..., description="角色: user 或 assistant")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(..., description="时间戳，ISO格式")


class MessageItemWithUser(MessageItem):
    username: Optional[str] = Field(None, description="用户名")


class ConversationHistoryResponse(BaseResponse[List[MessageItem]]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取对话历史成功", description="消息")


class ConversationHistoryAdminResponse(BaseResponse[List[MessageItemWithUser]]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取对话历史成功", description="消息")


class WebSocketTokenData(BaseModel):
    cmdToken: str = Field(..., description="停止指令Token")


class WebSocketTokenResponse(BaseResponse[WebSocketTokenData]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取WebSocket停止指令Token成功", description="消息")


class WebSocketMessage(BaseModel):
    type: Optional[str] = Field(None, description="消息类型: stop, completion等")
    chunk: Optional[str] = Field(None, description="内容块（流式响应）")
    error: Optional[str] = Field(None, description="错误信息")
    status: Optional[str] = Field(None, description="状态: finished等")
    message: Optional[str] = Field(None, description="消息")
    timestamp: Optional[int] = Field(None, description="时间戳（毫秒）")
    date: Optional[str] = Field(None, description="日期时间（ISO格式）")
    internal_cmd_token: Optional[str] = Field(None, alias="_internal_cmd_token", description="内部停止指令Token")
    
    class Config:
        populate_by_name = True


class ConversationItem(BaseModel):
    conversation_id: str = Field(..., description="会话ID")
    is_current: bool = Field(False, description="是否为当前会话")
    is_archived: bool = Field(False, description="是否已归档")
    message_count: int = Field(0, description="消息数量")
    last_message_time: Optional[str] = Field(None, description="最后一条消息时间")


class ConversationListResponse(BaseResponse[List[ConversationItem]]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取会话列表成功", description="消息")


class ConversationQueryParams(BaseModel):
    start_date: Optional[str] = Field(None, description="开始日期时间，格式: yyyy-MM-ddTHH:mm:ss")
    end_date: Optional[str] = Field(None, description="结束日期时间，格式: yyyy-MM-ddTHH:mm:ss")
    userid: Optional[int] = Field(None, description="用户ID（仅管理员接口）")


class ArchiveConversationData(BaseModel):
    conversation_id: str = Field(..., description="会话ID")
    archived_at: str = Field(..., description="归档时间，ISO格式")


class ArchiveConversationResponse(BaseResponse[ArchiveConversationData]):
    code: int = Field(200, description="状态码")
    message: str = Field("会话归档成功", description="提示信息")
