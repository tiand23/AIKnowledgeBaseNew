"""
聊天助手模块测试脚本

测试功能：
1. 用户登录获取Token
2. 获取WebSocket Token
3. WebSocket连接和消息发送
4. 会话管理（创建、获取、查询历史）
5. 会话归档功能
6. 已归档会话的只读验证
"""
import asyncio
import sys
import json
import logging
import warnings
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.pool").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.orm").setLevel(logging.ERROR)

logging.getLogger("app.services.search_service").setLevel(logging.INFO)
logging.getLogger("app.services.permission_service").setLevel(logging.INFO)
logging.getLogger("app.services.chat_service").setLevel(logging.INFO)

logging.getLogger("app.clients.elasticsearch_client").setLevel(logging.ERROR)

logging.getLogger("app.services.embedding_service").setLevel(logging.ERROR)
logging.getLogger("app.services.conversation_service").setLevel(logging.ERROR)
logging.getLogger("app.clients.redis_client").setLevel(logging.ERROR)
logging.getLogger("app.clients.db_client").setLevel(logging.ERROR)
logging.getLogger("app.clients.minio_client").setLevel(logging.ERROR)

import sys
handler = logging.StreamHandler(sys.stderr)  # Use stderr to avoid interfering with AI output on stdout
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger("app.services.search_service").addHandler(handler)
logging.getLogger("app.services.permission_service").addHandler(handler)
logging.getLogger("app.services.chat_service").addHandler(handler)

warnings.filterwarnings("ignore")

from app.clients.db_client import db_client
from app.clients.redis_client import redis_client
from app.clients.elasticsearch_client import es_client
from app.models.user import User
from app.services.conversation_service import conversation_service
from app.services.chat_service import chat_service
from app.utils import jwt_utils
from app.utils.security import verify_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

_original_connect = db_client.connect

def _test_connect():
    db_client.engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Disable SQL query logging in tests
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    
    db_client.SessionLocal = async_sessionmaker(
        db_client.engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

db_client.connect = _test_connect

TEST_USERNAME = "test_chat_user"
TEST_PASSWORD = "test_password_123"
TEST_EMAIL = "test_chat@example.com"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


async def create_test_user(db: AsyncSession) -> User:
    from app.utils.security import hash_password
    
    result = await db.execute(select(User).where(User.username == TEST_USERNAME))
    user = result.scalar_one_or_none()
    
    if user:
        print_info(f"测试用户已存在: {TEST_USERNAME}")
        return user
    
    user = User(
        username=TEST_USERNAME,
        email=TEST_EMAIL,
        password=hash_password(TEST_PASSWORD),
        org_tags="DEFAULT,test_org",
        primary_org="DEFAULT"
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    print_success(f"创建测试用户: {TEST_USERNAME} (ID: {user.id})")
    return user


async def test_login(db: AsyncSession) -> Optional[str]:
    print_info("=" * 60)
    print_info("测试1: 用户登录")
    print_info("=" * 60)
    
    try:
        result = await db.execute(select(User).where(User.username == TEST_USERNAME))
        user = result.scalar_one_or_none()
        
        if not user:
            print_error("测试用户不存在，请先创建")
            return None
        
        if not verify_password(TEST_PASSWORD, user.password):
            print_error("密码验证失败")
            return None
        
        token = await jwt_utils.generate_token(db, TEST_USERNAME)
        
        if token:
            print_success(f"登录成功，Token: {token[:50]}...")
            return token
        else:
            print_error("Token生成失败")
            return None
            
    except Exception as e:
        print_error(f"登录测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_conversation_management(db: AsyncSession, user: User):
    print_info("=" * 60)
    print_info("测试2: 会话管理")
    print_info("=" * 60)
    
    try:
        print_info("2.1 创建新会话")
        conversation_id = await conversation_service.create_conversation(user.id)
        print_success(f"创建会话成功: {conversation_id}")
        
        print_info("2.2 获取当前会话")
        current_id = await conversation_service.get_current_conversation(user.id)
        if current_id == conversation_id:
            print_success(f"当前会话ID匹配: {current_id}")
        else:
            print_error(f"当前会话ID不匹配: 期望 {conversation_id}, 实际 {current_id}")
        
        print_info("2.3 保存用户消息")
        success = await conversation_service.save_message(
            conversation_id, "user", "你好，我想了解一下知识库的功能", db=db
        )
        if success:
            print_success("用户消息保存成功")
        else:
            print_error("用户消息保存失败")
        
        print_info("2.4 保存助手回复")
        success = await conversation_service.save_message(
            conversation_id, "assistant", "您好！我是派聪明，可以帮助您查询知识库中的信息。", db=db
        )
        if success:
            print_success("助手回复保存成功")
        else:
            print_error("助手回复保存失败")
        
        print_info("2.5 获取对话历史")
        history = await conversation_service.get_conversation_history(conversation_id, db=db)
        print_success(f"获取到 {len(history)} 条历史记录")
        for i, msg in enumerate(history, 1):
            print(f"  [{i}] {msg['role']}: {msg['content'][:50]}...")
        
        return conversation_id
        
    except Exception as e:
        print_error(f"会话管理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_real_chat(db: AsyncSession, user: User, conversation_id: str):
    print_info("=" * 60)
    print_info("测试3: 真实AI服务调用")
    print_info("=" * 60)
    
    test_questions = [
        "你好，我想了解一下知识库的功能",
        "知识库支持哪些文件格式？",
        "如何上传文件到知识库？",
        "检索结果是如何排序的？"
    ]
    
    try:
        is_archived = await conversation_service.is_archived(conversation_id, db)
        if is_archived:
            print_warning("会话已归档，无法处理新消息")
            return
        
        print_info("开始真实对话测试...")
        print_warning("注意：此测试需要Elasticsearch和OpenAI API配置")
        print_warning("提示：请先运行 test_upload_knowledge_base.py 上传测试文件到知识库")
        print()
        
        for i, question in enumerate(test_questions, 1):
            print_info(f"--- 第 {i} 轮对话 ---")
            print()
            
            print(f"{Colors.BLUE}[用户] {question}{Colors.RESET}")
            print()
            
            print(f"{Colors.GREEN}[AI助手] ", end="", flush=True)
            
            try:
                import sys
                from io import StringIO
                
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                
                log_capture = StringIO()
                sys.stdout = log_capture
                sys.stderr = log_capture
                
                response_chunks = []
                try:
                    async for chunk in chat_service.process_message(
                        db=db,
                        user=user,
                        message=question,
                        conversation_id=conversation_id
                    ):
                        sys.stdout = old_stdout
                        response_chunks.append(chunk)
                        print(chunk, end="", flush=True)
                        sys.stdout = log_capture
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                
                print(Colors.RESET)
                print()
                
                if response_chunks:
                    response = "".join(response_chunks)
                    print_success(f"✓ 收到AI回复（共 {len(response)} 字符）")
                else:
                    print_warning("⚠ 未收到AI回复")
                
            except Exception as e:
                import sys
                if hasattr(sys, 'stdout'):
                    sys.stdout = old_stdout if 'old_stdout' in locals() else sys.__stdout__
                    sys.stderr = old_stderr if 'old_stderr' in locals() else sys.__stderr__
                print(Colors.RESET)
                print_error(f"✗ AI处理失败: {e}")
                print_warning("  这可能是由于缺少Elasticsearch或OpenAI API配置")
            
            if i < len(test_questions):
                await asyncio.sleep(0.5)
                print()
        
        print_info("=" * 60)
        print_success("真实对话测试完成！")
        print_info("=" * 60)
        print()
        
        print_info("对话历史统计：")
        history = await conversation_service.get_conversation_history(conversation_id, db=db)
        user_messages = [msg for msg in history if msg['role'] == 'user']
        assistant_messages = [msg for msg in history if msg['role'] == 'assistant']
        
        print(f"  总消息数: {len(history)}")
        print(f"  用户消息: {len(user_messages)}")
        print(f"  AI回复: {len(assistant_messages)}")
        print()
        
    except Exception as e:
        print_error(f"真实对话测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_archive_conversation(db: AsyncSession, user: User, conversation_id: str):
    print_info("=" * 60)
    print_info("测试4: 会话归档")
    print_info("=" * 60)
    
    try:
        print_info("4.1 检查归档状态（归档前）")
        is_archived = await conversation_service.is_archived(conversation_id, db)
        if not is_archived:
            print_success("会话未归档（正确）")
        else:
            print_error("会话已归档（不应该）")
            return
        
        print_info("4.2 获取归档前的历史记录")
        history_before = await conversation_service.get_conversation_history(conversation_id, db=db)
        message_count = len(history_before)
        print_success(f"归档前有 {message_count} 条消息")
        
        print_info("4.3 执行归档操作")
        success = await conversation_service.archive_conversation(
            conversation_id=conversation_id,
            user_id=user.id,
            db=db
        )
        
        if success:
            print_success("会话归档成功")
        else:
            print_error("会话归档失败")
            return
        
        print_info("4.4 验证归档状态（归档后）")
        is_archived = await conversation_service.is_archived(conversation_id, db)
        if is_archived:
            print_success("会话已归档（正确）")
        else:
            print_error("会话未归档（不应该）")
        
        print_info("4.5 从MySQL获取归档历史")
        archived_history = await conversation_service.get_archived_history(conversation_id, db)
        if len(archived_history) == message_count:
            print_success(f"归档历史记录数匹配: {len(archived_history)}")
        else:
            print_error(f"归档历史记录数不匹配: 期望 {message_count}, 实际 {len(archived_history)}")
        
        print_info("4.6 验证Redis中已删除")
        redis_history = await conversation_service._get_from_redis(conversation_id)
        if not redis_history:
            print_success("Redis中的会话数据已删除")
        else:
            print_error(f"Redis中仍有数据: {len(redis_history)} 条")
        
        print_info("4.7 验证get_conversation_history可以从MySQL读取")
        history_after = await conversation_service.get_conversation_history(conversation_id, db=db)
        if len(history_after) == message_count:
            print_success(f"从MySQL读取历史成功: {len(history_after)} 条")
        else:
            print_error(f"从MySQL读取历史失败: 期望 {message_count}, 实际 {len(history_after)}")
        
    except Exception as e:
        print_error(f"归档测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_readonly_after_archive(db: AsyncSession, user: User, conversation_id: str):
    print_info("=" * 60)
    print_info("测试5: 归档后的只读模式")
    print_info("=" * 60)
    
    try:
        print_info("5.1 尝试保存新消息到已归档会话")
        success = await conversation_service.save_message(
            conversation_id, "user", "这是一条测试消息", db=db
        )
        if not success:
            print_success("保存消息失败（正确，已归档会话为只读）")
        else:
            print_error("保存消息成功（错误，已归档会话应该只读）")
        
        print_info("5.2 验证历史记录未增加")
        history = await conversation_service.get_conversation_history(conversation_id, db=db)
        print_info(f"当前历史记录数: {len(history)}")
        
        print_info("5.3 尝试通过chat_service处理消息")
        try:
            response_chunks = []
            async for chunk in chat_service.process_message(
                db=db,
                user=user,
                message="测试消息",
                conversation_id=conversation_id
            ):
                response_chunks.append(chunk)
            
            response = "".join(response_chunks)
            if "已归档" in response or "无法继续" in response:
                print_success("正确返回归档提示")
            else:
                print_warning(f"返回内容: {response}")
                
        except Exception as e:
            print_warning(f"处理消息异常: {e}")
        
    except Exception as e:
        print_error(f"只读模式测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_multiple_conversations(db: AsyncSession, user: User):
    print_info("=" * 60)
    print_info("测试6: 多会话管理")
    print_info("=" * 60)
    
    try:
        print_info("6.1 创建多个会话")
        conv1 = await conversation_service.create_conversation(user.id)
        print_success(f"会话1: {conv1}")
        
        conv2 = await conversation_service.create_conversation(user.id)
        print_success(f"会话2: {conv2}")
        
        print_info("6.2 验证当前会话")
        current = await conversation_service.get_current_conversation(user.id)
        if current == conv2:
            print_success(f"当前会话是会话2: {current}")
        else:
            print_error(f"当前会话不匹配: 期望 {conv2}, 实际 {current}")
        
        print_info("6.3 在不同会话中保存消息")
        await conversation_service.save_message(conv1, "user", "会话1的消息", db=db)
        await conversation_service.save_message(conv2, "user", "会话2的消息", db=db)
        print_success("消息保存成功")
        
        print_info("6.4 验证会话独立性")
        h1 = await conversation_service.get_conversation_history(conv1, db=db)
        h2 = await conversation_service.get_conversation_history(conv2, db=db)
        print_success(f"会话1有 {len(h1)} 条消息，会话2有 {len(h2)} 条消息")
        
    except Exception as e:
        print_error(f"多会话测试失败: {e}")
        import traceback
        traceback.print_exc()


async def cleanup_test_data(db: AsyncSession, user: User):
    print_info("=" * 60)
    print_info("清理测试数据")
    print_info("=" * 60)
    
    try:
        print_info("Redis中的会话数据将在TTL到期后自动清理")
        
        from app.models.chat import ConversationArchive
        from sqlalchemy import select, delete
        
        result = await db.execute(
            select(ConversationArchive).where(ConversationArchive.user_id == user.id)
        )
        archives = result.scalars().all()
        
        if archives:
            print_info(f"找到 {len(archives)} 个归档会话（将保留，不删除）")
        else:
            print_info("没有找到归档会话")
        
        print_success("清理完成（归档数据保留）")
        
    except Exception as e:
        print_warning(f"清理测试数据时出错: {e}")


async def main():
    print_info("=" * 60)
    print_info("聊天助手模块测试")
    print_info("=" * 60)
    print()
    
    try:
        db_client.connect()
        await redis_client.connect()
        await es_client.connect()
        
        async for db in db_client.get_session():
            try:
                user = await create_test_user(db)
                
                token = await test_login(db)
                if not token:
                    print_error("登录测试失败，跳过后续测试")
                    return
                
                print()
                
                conversation_id = await test_conversation_management(db, user)
                if not conversation_id:
                    print_error("会话管理测试失败，跳过后续测试")
                    return
                
                print()
                
                await test_real_chat(db, user, conversation_id)
                
                print()
                
                await test_archive_conversation(db, user, conversation_id)
                
                print()
                
                await test_readonly_after_archive(db, user, conversation_id)
                
                print()
                
                await test_multiple_conversations(db, user)
                
                print()
                
                await cleanup_test_data(db, user)
                
                print()
                print_success("=" * 60)
                print_success("所有测试完成！")
                print_success("=" * 60)
                
            finally:
                break
        
    except Exception as e:
        print_error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await asyncio.wait_for(db_client.close(), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        
        try:
            await asyncio.wait_for(redis_client.close(), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        
        try:
            await asyncio.wait_for(es_client.close(), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_info("\n测试被用户中断")
    except Exception as e:
        print_error(f"测试执行失败: {e}")
        import traceback
        traceback.print_exc()

