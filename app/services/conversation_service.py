"""
会话管理服务 - 处理对话历史存储和会话ID管理
"""
from typing import List, Dict, Optional
import json
from datetime import datetime, timedelta
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.clients.redis_client import redis_client
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationService:
    
    def __init__(self):
        self.max_messages = settings.CONVERSATION_MAX_MESSAGES
        self.ttl_days = settings.CONVERSATION_TTL_DAYS
        self.ttl_seconds = self.ttl_days * 24 * 3600
    
    async def get_current_conversation(self, user_id: int) -> Optional[str]:
        """
        获取用户当前会话ID
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话ID，如果不存在则返回None
        """
        key = f"user:{user_id}:current_conversation"
        conversation_id = await redis_client.get(key)
        return conversation_id
    
    async def set_current_conversation(self, user_id: int, conversation_id: str) -> bool:
        """
        设置用户当前会话ID
        
        Args:
            user_id: 用户ID
            conversation_id: 会话ID
            
        Returns:
            是否成功
        """
        key = f"user:{user_id}:current_conversation"
        return await redis_client.set(key, conversation_id, expire=self.ttl_seconds)
    
    async def create_conversation(self, user_id: int) -> str:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            新创建的会话ID
        """
        conversation_id = str(uuid.uuid4())
        await self.set_current_conversation(user_id, conversation_id)
        await self.add_user_conversation(user_id, conversation_id)
        logger.info(f"为用户 {user_id} 创建新会话: {conversation_id}")
        return conversation_id
    
    async def get_or_create_conversation(self, user_id: int) -> str:
        """
        获取或创建会话ID
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话ID
        """
        conversation_id = await self.get_current_conversation(user_id)
        if not conversation_id:
            conversation_id = await self.create_conversation(user_id)
        else:
            await self.add_user_conversation(user_id, conversation_id)
        return conversation_id
    
    async def _get_from_redis(self, conversation_id: str) -> List[Dict[str, str]]:
        """
        从Redis获取对话历史（内部方法）
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            对话历史列表
        """
        key = f"conversation:{conversation_id}"
        data = await redis_client.get(key)
        
        if not data:
            return []
        
        try:
            parsed = json.loads(data)
            return parsed.get("messages", [])
        except json.JSONDecodeError as e:
            logger.error(f"解析对话历史失败: {e}, 会话ID: {conversation_id}")
            return []
    
    async def get_conversation_history(
        self, 
        conversation_id: str,
        db: Optional[AsyncSession] = None
    ) -> List[Dict[str, str]]:
        """
        获取对话历史记录（优先从Redis，如果已归档则从MySQL）
        
        Args:
            conversation_id: 会话ID
            db: 数据库会话（可选，检查归档时需提供）
            
        Returns:
            对话历史列表，每个元素包含 role, content, timestamp
        """
        history = await self._get_from_redis(conversation_id)
        
        if history:
            logger.debug(f"从Redis读取到会话 {conversation_id} 的 {len(history)} 条历史记录")
            return history
        
        if db:
            is_archived = await self.is_archived(conversation_id, db)
            if is_archived:
                history = await self.get_archived_history(conversation_id, db)
                logger.debug(f"从MySQL读取到会话 {conversation_id} 的 {len(history)} 条历史记录")
                return history
        
        logger.debug(f"会话 {conversation_id} 没有历史记录")
        return []
    
    async def save_message(
        self, 
        conversation_id: str, 
        role: str, 
        content: str,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """
        保存单条消息到对话历史（如果已归档则不保存）
        
        Args:
            conversation_id: 会话ID
            role: 角色（user 或 assistant）
            content: 消息内容
            db: 数据库会话（可选，用于检查归档状态）
            
        Returns:
            是否成功
        """
        if db:
            is_archived = await self.is_archived(conversation_id, db)
            if is_archived:
                logger.warning(f"会话 {conversation_id} 已归档，无法保存新消息")
                return False
        
        history = await self._get_from_redis(conversation_id)
        
        history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(history) > self.max_messages:
            history = history[-self.max_messages:]
        
        key = f"conversation:{conversation_id}"
        data = json.dumps({"messages": history}, ensure_ascii=False)
        
        success = await redis_client.set(key, data, expire=self.ttl_seconds)
        if success:
            logger.debug(f"保存消息到会话 {conversation_id}: {role}")
        
        return success
    
    async def save_conversation_round(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str
    ) -> bool:
        """
        保存一轮完整的对话（用户消息 + 助手回复）
        
        Args:
            conversation_id: 会话ID
            user_message: 用户消息
            assistant_message: 助手回复
            
        Returns:
            是否成功
        """
        await self.save_message(conversation_id, "user", user_message)
        
        await self.save_message(conversation_id, "assistant", assistant_message)
        
        return True
    
    async def clear_conversation(self, conversation_id: str) -> bool:
        """
        清空对话历史
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            是否成功
        """
        key = f"conversation:{conversation_id}"
        return await redis_client.delete(key)
    
    async def get_user_conversations(self, user_id: int) -> List[str]:
        """
        获取用户的所有会话ID列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话ID列表
        """
        key = f"user:{user_id}:conversations"
        data = await redis_client.get(key)
        
        if not data:
            return []
        
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return []
    
    async def verify_conversation_ownership(
        self,
        conversation_id: str,
        user_id: int,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """
        验证会话是否属于指定用户
        
        Args:
            conversation_id: 会话ID
            user_id: 用户ID
            db: 数据库会话（可选，用于检查归档会话）
            
        Returns:
            是否属于该用户
        """
        user_conversations = await self.get_user_conversations(user_id)
        if conversation_id in user_conversations:
            return True
        
        current_conversation = await self.get_current_conversation(user_id)
        if conversation_id == current_conversation:
            return True
        
        if db:
            from app.models.chat import ConversationArchive
            from sqlalchemy import select
            
            result = await db.execute(
                select(ConversationArchive).where(
                    ConversationArchive.conversation_id == conversation_id,
                    ConversationArchive.user_id == user_id
                )
            )
            if result.scalar_one_or_none():
                return True
        
        return False
    
    async def add_user_conversation(self, user_id: int, conversation_id: str) -> bool:
        """
        将会话ID添加到用户的会话列表
        
        Args:
            user_id: 用户ID
            conversation_id: 会话ID
            
        Returns:
            是否成功
        """
        conversations = await self.get_user_conversations(user_id)
        
        if conversation_id not in conversations:
            conversations.append(conversation_id)
            
            if len(conversations) > 50:
                conversations = conversations[-50:]
            
            key = f"user:{user_id}:conversations"
            data = json.dumps(conversations, ensure_ascii=False)
            return await redis_client.set(key, data, expire=self.ttl_seconds)
        
        return True
    
    async def is_archived(self, conversation_id: str, db: AsyncSession) -> bool:
        """
        检查会话是否已归档
        
        Args:
            conversation_id: 会话ID
            db: 数据库会话
            
        Returns:
            是否已归档
        """
        from app.models.chat import ConversationArchive
        from sqlalchemy import select
        
        result = await db.execute(
            select(ConversationArchive).where(
                ConversationArchive.conversation_id == conversation_id
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def archive_conversation(
        self,
        conversation_id: str,
        user_id: int,
        db: AsyncSession
    ) -> bool:
        """
        归档会话：从Redis迁移到MySQL，并从Redis删除
        
        Args:
            conversation_id: 会话ID
            user_id: 用户ID
            db: 数据库会话
            
        Returns:
            是否成功
        """
        from app.models.chat import ConversationArchive, ConversationMessage
        
        try:
            if await self.is_archived(conversation_id, db):
                logger.warning(f"会话 {conversation_id} 已经归档")
                return False
            
            history = await self._get_from_redis(conversation_id)
            
            if not history:
                logger.warning(f"会话 {conversation_id} 没有历史记录")
                return False
            
            archive = ConversationArchive(
                conversation_id=conversation_id,
                user_id=user_id,
                archived_at=datetime.now()
            )
            db.add(archive)
            await db.flush()  # Populate generated primary key
            
            messages = []
            for msg in history:
                timestamp_str = msg.get("timestamp", "")
                try:
                    if timestamp_str:
                        if 'T' in timestamp_str:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            timestamp = datetime.fromisoformat(timestamp_str)
                    else:
                        timestamp = datetime.now()
                except Exception as e:
                    logger.warning(f"解析时间戳失败: {timestamp_str}, 使用当前时间: {e}")
                    timestamp = datetime.now()
                
                messages.append(ConversationMessage(
                    conversation_id=conversation_id,
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    timestamp=timestamp
                ))
            
            db.add_all(messages)
            await db.commit()
            
            await self._delete_from_redis(conversation_id, user_id)
            
            logger.info(f"会话归档成功: conversation_id={conversation_id}, messages={len(messages)}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"归档会话失败: {e}", exc_info=True)
            return False
    
    async def _delete_from_redis(self, conversation_id: str, user_id: int):
        """
        从Redis删除会话相关数据
        
        Args:
            conversation_id: 会话ID
            user_id: 用户ID
        """
        key = f"conversation:{conversation_id}"
        await redis_client.delete(key)
        
        current_key = f"user:{user_id}:current_conversation"
        current_id = await redis_client.get(current_key)
        if current_id == conversation_id:
            await redis_client.delete(current_key)
    
    async def get_archived_history(
        self,
        conversation_id: str,
        db: AsyncSession
    ) -> List[Dict[str, str]]:
        """
        从MySQL获取已归档的对话历史
        
        Args:
            conversation_id: 会话ID
            db: 数据库会话
            
        Returns:
            对话历史列表
        """
        from app.models.chat import ConversationMessage
        from sqlalchemy import select
        
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.timestamp)
        )
        
        messages = result.scalars().all()
        
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages
        ]


conversation_service = ConversationService()
