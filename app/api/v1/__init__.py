"""
API v1 路由
"""
from fastapi import APIRouter
from app.api.v1 import auth_router
from app.api.v1 import document_router
from app.api.v1 import file_router
from app.api.v1 import admin_router
from app.api.v1 import chat_router
from app.api.v1 import profile_router
from app.api.v1 import eval_router

router = APIRouter()

router.include_router(auth_router.router, prefix="/auth", tags=["认证"])
router.include_router(document_router.router, prefix="/search", tags=["文档检索"])
router.include_router(file_router.upload_router, prefix="/upload", tags=["文件上传"])
router.include_router(file_router.documents_router, prefix="/documents", tags=["文档管理"])
router.include_router(profile_router.router, tags=["知识库场景"])
router.include_router(admin_router.router, prefix="/admin_router", tags=["管理员"])
router.include_router(chat_router.router, tags=["聊天助手"])
router.include_router(eval_router.router, prefix="/eval", tags=["評価"])
