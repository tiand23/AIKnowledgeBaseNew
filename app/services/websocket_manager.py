"""
WebSocket 连接管理器 - 管理所有 WebSocket 连接和会话隔离
"""
from typing import Dict, Optional, Set
from fastapi import WebSocket
from app.models.user import User
import uuid
import asyncio
from datetime import datetime
from app.utils.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class WebSocketConnection:
    
    def __init__(
        self,
        connection_id: str,
        websocket: WebSocket,
        user: User,
        conversation_id: str,
        created_at: datetime
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.user = user
        self.conversation_id = conversation_id
        self.created_at = created_at
        self.last_activity = created_at
        self.last_ping_time: Optional[datetime] = None  # Last ping sent timestamp
        self.last_pong_time: Optional[datetime] = None  # Last pong received timestamp
        self.is_active = True
        self.current_stop_token: Optional[str] = None
        self.pending_ping = False  # Whether there is an outstanding ping
    
    def update_activity(self):
        self.last_activity = datetime.now()
    
    def is_idle(self, timeout_seconds: int) -> bool:
        """
        检查连接是否空闲（超过超时时间）
        
        Args:
            timeout_seconds: 超时时间（秒），0表示不超时
            
        Returns:
            是否空闲
        """
        if timeout_seconds <= 0:
            return False
        
        idle_seconds = (datetime.now() - self.last_activity).total_seconds()
        return idle_seconds > timeout_seconds
    
    def __repr__(self):
        return (
            f"<WebSocketConnection("
            f"id={self.connection_id}, "
            f"user_id={self.user.id}, "
            f"conversation_id={self.conversation_id}, "
            f"active={self.is_active}"
            f")>"
        )


class WebSocketConnectionManager:
    """
    WebSocket 连接管理器
    
    核心功能：
    1. 管理所有活跃的 WebSocket 连接
    2. 为每个连接分配独立的会话ID（连接级别隔离）
    3. 支持连接状态查询
    4. 异常断开检测和清理
    5. 基本消息路由（点对点）
    """
    
    def __init__(self):
        self._connections: Dict[str, WebSocketConnection] = {}
        
        self._user_connections: Dict[int, Set[str]] = {}
        
        self._conversation_connections: Dict[str, Set[str]] = {}
        
        self._lock = asyncio.Lock()
    
    async def connect(
        self,
        websocket: WebSocket,
        user: User,
        conversation_id: str
    ) -> str:
        """
        建立新的 WebSocket 连接
        
        Args:
            websocket: WebSocket 连接对象
            user: 用户对象
            conversation_id: 会话ID（必填，由调用方验证和提供）
            
        Returns:
            连接ID
            
        Raises:
            ValueError: 如果超过连接数限制或会话ID无效
        """
        if not conversation_id:
            raise ValueError("会话ID不能为空")
        
        async with self._lock:
            if len(self._connections) >= settings.WEBSOCKET_MAX_CONNECTIONS_PER_INSTANCE:
                error_msg = (
                    f"达到单实例最大连接数限制: "
                    f"{settings.WEBSOCKET_MAX_CONNECTIONS_PER_INSTANCE}"
                )
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            user_connections = self._user_connections.get(user.id, set())
            if len(user_connections) >= settings.WEBSOCKET_MAX_CONNECTIONS_PER_USER:
                error_msg = (
                    f"用户 {user.id} 达到最大连接数限制: "
                    f"{settings.WEBSOCKET_MAX_CONNECTIONS_PER_USER}"
                )
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            connection_id = f"ws_{uuid.uuid4().hex[:16]}"
            
            connection = WebSocketConnection(
                connection_id=connection_id,
                websocket=websocket,
                user=user,
                conversation_id=conversation_id,
                created_at=datetime.now()
            )
            
            self._connections[connection_id] = connection
            
            if user.id not in self._user_connections:
                self._user_connections[user.id] = set()
            self._user_connections[user.id].add(connection_id)
            
            if conversation_id not in self._conversation_connections:
                self._conversation_connections[conversation_id] = set()
            self._conversation_connections[conversation_id].add(connection_id)
            
            logger.info(
                f"WebSocket连接建立: connection_id={connection_id}, "
                f"user_id={user.id}, conversation_id={conversation_id}"
            )
            
            return connection_id
    
    async def disconnect(self, connection_id: str):
        """
        断开连接并清理资源
        
        Args:
            connection_id: 连接ID
        """
        async with self._lock:
            if connection_id not in self._connections:
                logger.warning(f"尝试断开不存在的连接: {connection_id}")
                return
            
            connection = self._connections[connection_id]
            
            if connection.user.id in self._user_connections:
                self._user_connections[connection.user.id].discard(connection_id)
                if not self._user_connections[connection.user.id]:
                    del self._user_connections[connection.user.id]
            
            if connection.conversation_id in self._conversation_connections:
                self._conversation_connections[connection.conversation_id].discard(connection_id)
                if not self._conversation_connections[connection.conversation_id]:
                    del self._conversation_connections[connection.conversation_id]
            
            del self._connections[connection_id]
            
            logger.info(
                f"WebSocket连接断开: connection_id={connection_id}, "
                f"user_id={connection.user.id}"
            )
    
    def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """
        获取连接对象
        
        Args:
            connection_id: 连接ID
            
        Returns:
            连接对象，如果不存在则返回 None
        """
        return self._connections.get(connection_id)
    
    def get_conversation_id(self, connection_id: str) -> Optional[str]:
        """
        获取连接绑定的会话ID
        
        Args:
            connection_id: 连接ID
            
        Returns:
            会话ID，如果连接不存在则返回 None
        """
        connection = self.get_connection(connection_id)
        return connection.conversation_id if connection else None
    
    def get_user_connections(self, user_id: int) -> Set[str]:
        """
        获取用户的所有连接ID
        
        Args:
            user_id: 用户ID
            
        Returns:
            连接ID集合
        """
        return self._user_connections.get(user_id, set()).copy()
    
    def get_conversation_connections(self, conversation_id: str) -> Set[str]:
        """
        获取会话的所有连接ID
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            连接ID集合
        """
        return self._conversation_connections.get(conversation_id, set()).copy()
    
    async def send_to_connection(
        self,
        connection_id: str,
        message: dict
    ) -> bool:
        """
        向指定连接发送消息（点对点）
        
        Args:
            connection_id: 连接ID
            message: 消息字典
            
        Returns:
            是否发送成功
        """
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection or not connection.is_active:
                logger.warning(f"尝试向无效连接发送消息: {connection_id}")
                return False
        
        try:
            await connection.websocket.send_json(message)
            async with self._lock:
                conn = self._connections.get(connection_id)
                if conn:
                    conn.update_activity()
            return True
        except Exception as e:
            logger.error(
                f"向连接发送消息失败: connection_id={connection_id}, "
                f"error={e}"
            )
            async with self._lock:
                conn = self._connections.get(connection_id)
                if conn:
                    conn.is_active = False
            return False
    
    def get_statistics(self) -> dict:
        """
        获取连接统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "total_connections": len(self._connections),
            "total_users": len(self._user_connections),
            "total_conversations": len(self._conversation_connections),
            "connections_per_user": {
                user_id: len(conn_ids)
                for user_id, conn_ids in self._user_connections.items()
            }
        }
    
    async def send_heartbeat_ping(self, connection_id: str) -> bool:
        """
        向连接发送心跳ping消息
        
        Args:
            connection_id: 连接ID
            
        Returns:
            是否发送成功
        """
        connection = self.get_connection(connection_id)
        if not connection:
            return False
        
        async with self._lock:
            if not connection.is_active:
                return False
            
            if connection.pending_ping:
                return True
        
        try:
            ping_message = {
                "type": "ping",
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            await asyncio.wait_for(
                connection.websocket.send_json(ping_message),
                timeout=1.0
            )
            async with self._lock:
                conn = self._connections.get(connection_id)
                if conn:
                    conn.last_ping_time = datetime.now()
                    conn.pending_ping = True
            return True
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(
                f"发送心跳ping失败: connection_id={connection_id}, error={e}"
            )
            async with self._lock:
                conn = self._connections.get(connection_id)
                if conn:
                    conn.is_active = False
            return False
    
    async def handle_pong(self, connection_id: str):
        """
        处理客户端返回的pong响应
        
        Args:
            connection_id: 连接ID
        """
        async with self._lock:
            connection = self._connections.get(connection_id)
            if connection:
                connection.last_pong_time = datetime.now()
                connection.pending_ping = False
                connection.update_activity()
    
    async def cleanup_inactive_connections(self):
        """
        清理不活跃的连接（心跳检测）
        
        检测策略：
        1. 检查连接是否空闲（超过IDLE_TIMEOUT）
        2. 发送ping检测连接是否响应
        3. 清理无响应的连接
        """
        if not self._connections:
            return
        
        now = datetime.now()
        inactive_connections = []
        ping_connections = []
        
        async with self._lock:
            connection_ids = list(self._connections.keys())
        
        for connection_id in connection_ids:
            connection = self.get_connection(connection_id)
            if not connection:
                continue
            
            if not connection.is_active:
                inactive_connections.append(connection_id)
                continue
            
            if settings.WEBSOCKET_IDLE_TIMEOUT > 0:
                if connection.is_idle(settings.WEBSOCKET_IDLE_TIMEOUT):
                    logger.debug(
                        f"连接空闲超时: connection_id={connection_id}, "
                        f"idle_seconds={(now - connection.last_activity).total_seconds():.1f}"
                    )
                    ping_connections.append(connection_id)
                    continue
            
            if connection.pending_ping and connection.last_ping_time:
                ping_timeout = (now - connection.last_ping_time).total_seconds()
                if ping_timeout > 5.0:  # Consider the connection stale after 5s ping timeout
                    logger.warning(
                        f"心跳ping超时: connection_id={connection_id}, "
                        f"timeout={ping_timeout:.1f}s"
                    )
                    async with self._lock:
                        conn = self._connections.get(connection_id)
                        if conn:
                            conn.is_active = False
                    inactive_connections.append(connection_id)
                    continue
        
        for connection_id in ping_connections:
            success = await self.send_heartbeat_ping(connection_id)
            if not success:
                inactive_connections.append(connection_id)
        
        for connection_id in inactive_connections:
            await self.disconnect(connection_id)
        
        if inactive_connections:
            logger.info(
                f"心跳检测清理了 {len(inactive_connections)} 个不活跃连接"
            )


websocket_manager = WebSocketConnectionManager()
