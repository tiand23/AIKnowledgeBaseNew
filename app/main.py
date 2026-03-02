"""
FastAPI 应用入口
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from datetime import datetime
import asyncio
from sqlalchemy import text
from app.api import router as api_router
from app.core.config import settings
from app.core.exceptions import BusinessException
from app.core.error_codes import ErrorCode, get_error_code_by_string
from app.clients.redis_client import redis_client
from app.clients.db_client import db_client
from app.clients.minio_client import minio_client
from app.clients.elasticsearch_client import es_client
from app.clients.kafka_client import kafka_client
from app.models import Base
from app.services.document_processor_service import document_processor_service
from app.services.intent_keyword_config_service import intent_keyword_config_service
from app.services.master_data_service import master_data_service
from app.services.websocket_manager import websocket_manager
from app.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def connect_es_with_retry(max_attempts: int = 10, base_delay: float = 1.5) -> None:
    """
    连接 Elasticsearch（带重试），避免容器冷启动时 ES 尚未就绪导致应用直接退出。
    """
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            await es_client.connect()
            if attempt > 1:
                logger.info(f"Elasticsearch 在第 {attempt} 次重试后连接成功")
            return
        except Exception as e:
            last_error = e
            if attempt >= max_attempts:
                break
            delay = min(base_delay * attempt, 8.0)
            logger.warning(
                f"Elasticsearch 尚未就绪（attempt={attempt}/{max_attempts}），{delay:.1f}s 后重试: {e}"
            )
            await asyncio.sleep(delay)
    raise last_error if last_error else RuntimeError("Elasticsearch connect failed")


async def ensure_runtime_schema() -> None:
    """
    运行时兜底 schema 修复（仅做向后兼容，避免旧库缺列导致启动失败）。
    """
    if not db_client.engine:
        return
    try:
        async with db_client.engine.begin() as conn:
            try:
                await conn.execute(
                    text("ALTER TABLE file_upload ADD COLUMN kb_profile VARCHAR(32) NOT NULL DEFAULT 'general'")
                )
                logger.info("已补齐 file_upload.kb_profile 列")
            except Exception:
                pass

            try:
                await conn.execute(text("UPDATE file_upload SET kb_profile = 'general' WHERE kb_profile IS NULL"))
            except Exception:
                pass

            try:
                await conn.execute(text("CREATE INDEX idx_kb_profile ON file_upload (kb_profile)"))
            except Exception:
                pass

            try:
                await conn.execute(
                    text("CREATE UNIQUE INDEX uk_chunk_file_index ON chunk_info (file_md5, chunk_index)")
                )
            except Exception:
                pass

            try:
                await conn.execute(
                    text("ALTER TABLE image_blocks ADD COLUMN match_mode VARCHAR(32)")
                )
                logger.info("已补齐 image_blocks.match_mode 列")
            except Exception:
                pass

            try:
                await conn.execute(
                    text("ALTER TABLE image_blocks ADD COLUMN match_confidence INTEGER")
                )
                logger.info("已补齐 image_blocks.match_confidence 列")
            except Exception:
                pass

            try:
                await conn.execute(
                    text("ALTER TABLE image_blocks ADD COLUMN match_reason TEXT")
                )
                logger.info("已补齐 image_blocks.match_reason 列")
            except Exception:
                pass

            try:
                await conn.execute(
                    text("CREATE INDEX idx_image_blocks_sheet_page ON image_blocks (sheet, page)")
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"运行时 schema 修复跳过: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("FastAPI 应用启动中...")
    logger.info(f"应用名称: {settings.APP_NAME}")
    logger.info(f"调试模式: {settings.DEBUG}")

    kafka_consumer_tasks = []
    kafka_consumers = []
    websocket_heartbeat_task = None

    try:
        db_client.connect()
        async with db_client.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await ensure_runtime_schema()
        async with db_client.SessionLocal() as session:
            await master_data_service.ensure_default_org_tag(session)
            await session.commit()
            await intent_keyword_config_service.sync_runtime_from_db(session)
        logger.info("数据库连接与表结构初始化成功")

        await redis_client.connect()
        logger.info("Redis 连接成功")

        minio_client.connect()
        logger.info("MinIO 对象存储连接成功")

        await connect_es_with_retry()
        logger.info("Elasticsearch 连接成功")

        await kafka_client.connect()
        logger.info("Kafka 连接成功")

        try:
            consumer_instances = max(1, int(settings.KAFKA_CONSUMER_INSTANCES))

            for idx in range(consumer_instances):
                consumer = await kafka_client.create_consumer(
                    topics=["document_parse"],
                    group_id="document_processor_group",
                    auto_offset_reset='latest',  # Start from latest offsets for new group members
                    enable_auto_commit=False
                )
                kafka_consumers.append(consumer)

                async def consume_loop(worker_idx: int, worker_consumer):
                    try:
                        logger.info(
                            "Kafka 消费者已启动: worker=%s/%s, topic=document_parse",
                            worker_idx + 1,
                            consumer_instances,
                        )
                        await kafka_client.consume_messages(
                            consumer=worker_consumer,
                            callback=document_processor_service.handle_kafka_message
                        )
                    except asyncio.CancelledError:
                        logger.info("Kafka 消费者任务已取消: worker=%s", worker_idx + 1)
                    except Exception as e:
                        logger.error(f"Kafka 消费者异常: worker={worker_idx + 1}, err={e}", exc_info=True)

                kafka_consumer_tasks.append(asyncio.create_task(consume_loop(idx, consumer)))

            logger.info("Kafka 文档处理消费者已启动: instances=%s", len(kafka_consumers))
            
        except Exception as e:
            logger.warning(f"启动 Kafka 消费者失败（可选服务）: {e}")
            logger.warning("文档处理功能将不可用，但应用可以继续运行")

        async def heartbeat_loop():
            try:
                while True:
                    await asyncio.sleep(settings.WEBSOCKET_CLEANUP_INTERVAL)
                    try:
                        await websocket_manager.cleanup_inactive_connections()
                    except Exception as e:
                        logger.error(f"心跳检测异常: {e}", exc_info=True)
            except asyncio.CancelledError:
                logger.info("WebSocket 心跳检测任务已取消")
            except Exception as e:
                logger.error(f"WebSocket 心跳检测任务异常: {e}", exc_info=True)
        
        websocket_heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info(
            f"WebSocket 心跳检测已启动，清理间隔: {settings.WEBSOCKET_CLEANUP_INTERVAL}秒"
        )

        logger.info("FastAPI 应用启动完成！")
        logger.info("=" * 60)
    except Exception as e:
        logger.critical(f"应用启动失败: {e}", exc_info=True)
        raise
    
    yield

    logger.info("=" * 60)
    logger.info("FastAPI 应用关闭中...")

    try:
        if websocket_heartbeat_task and not websocket_heartbeat_task.done():
            logger.info("正在停止 WebSocket 心跳检测...")
            websocket_heartbeat_task.cancel()
            try:
                await asyncio.wait_for(websocket_heartbeat_task, timeout=5.0)
            except asyncio.CancelledError:
                logger.info("WebSocket 心跳检测任务已停止")
            except asyncio.TimeoutError:
                logger.warning("WebSocket 心跳检测停止超时")
        
        if kafka_consumer_tasks:
            logger.info("正在停止 Kafka 消费者任务: count=%s", len(kafka_consumer_tasks))
            for task in kafka_consumer_tasks:
                if not task.done():
                    task.cancel()
            for task in kafka_consumer_tasks:
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.CancelledError:
                    pass
                except asyncio.TimeoutError:
                    logger.warning("Kafka 消费者任务停止超时")
            logger.info("Kafka 消费者任务已停止")

        if kafka_consumers:
            for consumer in kafka_consumers:
                try:
                    await consumer.stop()
                except Exception as e:
                    logger.warning(f"停止 Kafka 消费者时出错: {e}")

        await db_client.close()
        logger.info("MySQL 连接已关闭")

        await redis_client.close()
        logger.info("Redis 连接已关闭")

        minio_client.close()
        logger.info("MinIO 连接已关闭")

        await es_client.close()
        logger.info("Elasticsearch 连接已关闭")

        await kafka_client.close()
        logger.info("Kafka 连接已关闭")

        logger.info("FastAPI 应用已安全关闭")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"应用关闭时出错: {e}", exc_info=True)


app = FastAPI(
    title=settings.APP_NAME,
    description="FastAPI Service",
    version="0.1.0",  # Application version
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    logger.warning(
        f"业务异常: {exc.code} - {exc.message}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "code": exc.code,
        }
    )
    error_code = get_error_code_by_string(exc.code) if isinstance(exc.code, str) else exc.code
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": error_code,
            "message": exc.message,
            "data": exc.data
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    log_extra = {
        "path": request.url.path,
        "method": request.method,
        "status_code": exc.status_code,
    }
    if exc.status_code in {401, 403}:
        logger.info(f"HTTP 异常: {exc.status_code} - {exc.detail}", extra=log_extra)
    else:
        logger.warning(f"HTTP 异常: {exc.status_code} - {exc.detail}", extra=log_extra)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail if exc.detail else f"HTTP {exc.status_code} Error",
            "data": None
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"请求参数验证失败: {errors}",
        extra={
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "code": ErrorCode.VALIDATION_ERROR,
            "message": "请求参数验证失败",
            "data": {"errors": errors}
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"未捕获的异常: {str(exc)}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
        }
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": ErrorCode.INTERNAL_SERVER_ERROR,
            "message": "服务器内部错误" if not settings.DEBUG else str(exc),
            "data": None
        }
    )


app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "code": ErrorCode.SUCCESS,
        "message": "FastAPI 服务运行中",
        "data": {
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/health")
async def health_check():
    return {
        "code": ErrorCode.SUCCESS,
        "message": "服务健康",
        "data": {"status": "healthy"}
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """
    详细健康检查 - 包括所有服务状态和连接池监控
    
    返回:
        - 数据库连接池状态
        - Redis连接状态
        - Elasticsearch连接状态
        - MinIO连接状态
        - Kafka连接状态（如果启用）
    """
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }
    
    overall_healthy = True
    
    try:
        if not db_client.SessionLocal:
            health_status["services"]["database"] = {
                "status": "uninitialized",
                "error": "数据库未初始化"
            }
            overall_healthy = False
        else:
            db_health = await db_client.health_check()
            db_pool_status = db_client.get_pool_status()
            health_status["services"]["database"] = {
                "status": "healthy" if db_health else "unhealthy",
                "connection_pool": db_pool_status
            }
            if not db_health:
                overall_healthy = False
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        overall_healthy = False
    
    try:
        if not redis_client.redis:
            health_status["services"]["redis"] = {
                "status": "uninitialized",
                "error": "Redis未初始化"
            }
            overall_healthy = False
        else:
            redis_health = await redis_client.health_check()
            redis_pool_status = redis_client.get_pool_status()
            health_status["services"]["redis"] = {
                "status": "healthy" if redis_health else "unhealthy",
                "connection_pool": redis_pool_status
            }
            if not redis_health:
                overall_healthy = False
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "error",
            "error": str(e)
        }
        overall_healthy = False
    
    try:
        if not es_client.client:
            health_status["services"]["elasticsearch"] = {
                "status": "uninitialized",
                "error": "Elasticsearch未初始化"
            }
            overall_healthy = False
        else:
            es_health = await es_client.health_check()
            health_status["services"]["elasticsearch"] = {
                "status": "healthy" if es_health else "unhealthy"
            }
            if not es_health:
                overall_healthy = False
    except Exception as e:
        health_status["services"]["elasticsearch"] = {
            "status": "error",
            "error": str(e)
        }
        overall_healthy = False
    
    try:
        if not minio_client.client:
            health_status["services"]["minio"] = {
                "status": "uninitialized",
                "error": "MinIO未初始化"
            }
            overall_healthy = False
        else:
            minio_health = minio_client.health_check()
            minio_status = minio_client.get_status()
            health_status["services"]["minio"] = {
                "status": "healthy" if minio_health else "unhealthy",
                "details": minio_status
            }
            if not minio_health:
                overall_healthy = False
    except Exception as e:
        health_status["services"]["minio"] = {
            "status": "error",
            "error": str(e)
        }
        overall_healthy = False
    
    try:
        if not kafka_client.producer:
            health_status["services"]["kafka"] = {
                "status": "uninitialized",
                "error": "Kafka未初始化"
            }
        else:
            kafka_health = await kafka_client.health_check()
            health_status["services"]["kafka"] = {
                "status": "healthy" if kafka_health else "unhealthy"
            }
    except Exception as e:
        health_status["services"]["kafka"] = {
            "status": "error",
            "error": str(e)
        }
    
    health_status["status"] = "healthy" if overall_healthy else "degraded"
    
    return {
        "code": ErrorCode.SUCCESS if overall_healthy else ErrorCode.INTERNAL_SERVER_ERROR,
        "message": "所有服务正常" if overall_healthy else "部分服务异常",
        "data": health_status
    }
