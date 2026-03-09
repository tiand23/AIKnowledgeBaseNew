"""
用户认证接口
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from app.api.deps import get_db, get_current_user
from app.utils.logger import get_logger
from app.schemas.auth import (
    CaptchaResponse,
    RegisterOrgTagOption,
    RegisterOrgTagOptionsResponse,
    UserRegisterRequest,
    UserRegisterResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserInfoResponse,
    UserInfoData,
    UserListResponse,
    UserListItem,
)
from app.models.user import User, UserRole
from typing import List, Optional
from app.clients.redis_client import redis_client
from app.core.config import settings
from app.utils.captcha import (
    generate_captcha_text,
    generate_captcha_image,
)
from app.utils.security import (
    hash_password,
    verify_password,
    generate_uuid,
)
from app.utils import jwt_utils
from app.utils.rate_limit import (
    check_captcha_rate_limit,
    check_register_rate_limit,
)
from app.models.organization import OrganizationTag
from app.services.master_data_service import master_data_service
from pydantic import ValidationError

logger = get_logger(__name__)


router = APIRouter()

REGISTER_ORG_TAG_PRESETS = [
    {"tag_id": "DEFAULT", "name": "全体公開", "description": "全ユーザー共通で参照可能"},
    {"tag_id": "BUSINESS", "name": "業務部門", "description": "業務・企画系ドキュメント"},
    {"tag_id": "DEV", "name": "開発部門", "description": "設計・実装・技術資料"},
    {"tag_id": "OPS", "name": "運用部門", "description": "運用・障害対応・保守資料"},
]


@router.get("/register/org-tags", response_model=RegisterOrgTagOptionsResponse)
async def get_register_org_tag_options(
    db: AsyncSession = Depends(get_db),
):
    """
    注册页组织标签选项（公开接口）：
    - 排除用户私有标签 PRIVATE_*
    - 返回可用于注册绑定权限的组织标签
    """
    rows = await db.execute(
        select(OrganizationTag)
        .where(~OrganizationTag.tag_id.like("PRIVATE\\_%", escape="\\"))
        .order_by(OrganizationTag.tag_id.asc())
    )
    tags = rows.scalars().all()
    if tags:
        data = [
            RegisterOrgTagOption(
                tagId=tag.tag_id,
                name=tag.name,
                description=tag.description,
            )
            for tag in tags
        ]
    else:
        data = [
            RegisterOrgTagOption(
                tagId=item["tag_id"],
                name=item["name"],
                description=item["description"],
            )
            for item in REGISTER_ORG_TAG_PRESETS
        ]
    return RegisterOrgTagOptionsResponse(
        code=200,
        message="注册组织标签列表获取成功",
        data=data,
    )


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha(request: Request):
    """
    获取图形验证码

    - 速率限制：每IP每分钟最多10次
    - 返回：验证码ID + Base64图片
    """
    client_ip = request.client.host
    logger.debug(f"请求图形验证码 | IP: {client_ip}")

    try:
        await check_captcha_rate_limit(request)

        captcha_id = generate_uuid()
        captcha_text = generate_captcha_text()
        captcha_image = generate_captcha_image(captcha_text)

        key = f"captcha:{captcha_id}"
        await redis_client.set(
            key, captcha_text, expire=settings.CAPTCHA_EXPIRE_SECONDS
        )

        logger.info(f"生成图形验证码成功 | IP: {client_ip} | ID: {captcha_id[:8]}...")

        from app.schemas.auth import CaptchaData
        return CaptchaResponse(
            code=200,
            message="获取验证码成功",
            data=CaptchaData(captcha_id=captcha_id, captcha_image=captcha_image)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成图形验证码失败 | IP: {client_ip}", exc_info=True)
        raise HTTPException(status_code=500, detail="验证码生成失败")


@router.post("/register", response_model=UserRegisterResponse)
async def register(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册
    - 创建用户
    - 返回访问token（自动登录）
    """
    await check_register_rate_limit(request)

    raw_payload = {}
    content_type = (request.headers.get("content-type") or "").lower()
    try:
        if "application/json" in content_type:
            raw_payload = await request.json()
        else:
            form = await request.form()
            raw_payload = dict(form)
    except Exception:
        raw_payload = {}

    try:
        request_data = UserRegisterRequest(
            username=str(raw_payload.get("username", "")).strip(),
            email=str(raw_payload.get("email", "")).strip(),
            password=str(raw_payload.get("password", "")),
            org_tags=(
                raw_payload.get("org_tags")
                if isinstance(raw_payload.get("org_tags"), list)
                else raw_payload.get("orgTags")
                if isinstance(raw_payload.get("orgTags"), list)
                else []
            ),
            primary_org=str(
                raw_payload.get("primary_org")
                or raw_payload.get("primaryOrg")
                or ""
            ).strip() or None,
        )
    except ValidationError as e:
        errors = []
        for err in e.errors():
            field = ".".join([str(x) for x in err.get("loc", []) if x != "body"]) or "field"
            msg = err.get("msg", "invalid")
            errors.append(f"{field}: {msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="注册参数错误: " + "; ".join(errors)
        )

    result = await db.execute(select(User).where(User.email == request_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已被注册"
        )

    result = await db.execute(
        select(User).where(User.username == request_data.username)
    )
    existing_username = result.scalar_one_or_none()
    if existing_username:
        raise HTTPException(status_code=400, detail="用户名已存在")

    try:
        selected_org_tags = [str(x).strip().upper() for x in (request_data.org_tags or []) if str(x).strip()]
        selected_org_tags = [x for x in selected_org_tags if not x.startswith("PRIVATE_")]
        selected_org_tags = list(dict.fromkeys(selected_org_tags))
        requested_primary_org = (request_data.primary_org or "").strip().upper() or None
        if requested_primary_org and requested_primary_org not in selected_org_tags:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="主组织必须在已选择的组织标签中",
            )

        hashed_pwd = hash_password(request_data.password)
        new_user = User(
            username=request_data.username,
            email=request_data.email,
            password=hashed_pwd,
            role=UserRole.USER,
        )
        db.add(new_user)
        await db.flush()  # Materialize user ID without committing yet

        await master_data_service.ensure_default_org_tag(db, creator_user_id=int(new_user.id))
        
        private_tag_id = f"PRIVATE_{request_data.username}"
        private_tag = OrganizationTag(
            tag_id=private_tag_id,
            name=f"我的组织-{request_data.username}",
            description=f"用户 {request_data.username} 的私人组织",
            parent_tag=None,  # Top-level tag (no parent)
            created_by=new_user.id,
        )
        db.add(private_tag)

        if selected_org_tags:
            tag_rows = await db.execute(
                select(OrganizationTag.tag_id).where(OrganizationTag.tag_id.in_(selected_org_tags))
            )
            existing_tags = {row[0] for row in tag_rows.all()}
            preset_map = {item["tag_id"]: item for item in REGISTER_ORG_TAG_PRESETS}
            for tag_id in selected_org_tags:
                if tag_id in existing_tags:
                    continue
                preset = preset_map.get(tag_id)
                if not preset:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"无效组织标签: {tag_id}",
                    )
                db.add(
                    OrganizationTag(
                        tag_id=tag_id,
                        name=preset["name"],
                        description=preset["description"],
                        parent_tag=None,
                        created_by=new_user.id,
                    )
                )

        merged_tags = [private_tag_id] + selected_org_tags
        new_user.org_tags = ",".join(merged_tags)
        new_user.primary_org = requested_primary_org or (selected_org_tags[0] if selected_org_tags else private_tag_id)
        
        await db.commit()
        await db.refresh(new_user)
    except Exception as e:
        await db.rollback()
        if isinstance(e, HTTPException):
            raise
        error_type = type(e).__name__
        error_detail = str(e)
        logger.error(f"用户注册失败: {error_type}: {error_detail}", exc_info=True)
        
        if "IntegrityError" in error_type or "duplicate" in error_detail.lower():
            detail_msg = "用户名或邮箱已存在，请使用其他信息注册。"
        elif "database" in error_detail.lower() or "Database" in error_type:
            detail_msg = "数据库操作失败，请稍后重试。如果问题持续，请联系管理员。"
        elif "connection" in error_detail.lower() or "Connection" in error_type:
            detail_msg = "无法连接到数据库，请稍后重试。"
        else:
            detail_msg = f"注册失败: {error_detail[:100]}（错误类型: {error_type}）"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_msg
        )

    access_token = await jwt_utils.generate_token(db, new_user.username)

    from app.schemas.auth import UserRegisterData
    return UserRegisterResponse(
        code=200,
        message="注册成功",
        data=UserRegisterData(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            access_token=access_token,
            token_type="bearer"
        )
    )


@router.post("/login", response_model=UserLoginResponse)
async def login(request_data: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    用户登录

    - 接收用户登录请求，获取用户名和密码
    - 查询用户记录并验证密码
    - 加载用户组织标签信息（通过 generate_token 自动加载）
    - 生成包含用户信息和组织标签的 JWT Token
    - 返回登录成功响应和 Token
    """
    result = await db.execute(select(User).where(User.username == request_data.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    if not verify_password(request_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    access_token = await jwt_utils.generate_token(db, user.username)

    from app.schemas.auth import UserLoginData
    return UserLoginResponse(
        code=200,
        message="登录成功",
        data=UserLoginData(
            access_token=access_token,
            token_type="bearer",
            user_id=user.id,
            username=user.username,
            email=user.email
        )
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前登录用户信息
    
    - 从 JWT token 中提取用户信息
    - 返回用户详细信息（包含组织标签）
    """
    org_tags_list: List[str] = []
    if current_user.org_tags:
        org_tags_list = [tag.strip() for tag in current_user.org_tags.split(",") if tag.strip()]
    
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    
    return UserInfoResponse(
        code=200,
        message="Success",
        data=UserInfoData(
            id=current_user.id,
            username=current_user.username,
            role=role_str,
            orgTags=org_tags_list,
            primaryOrg=current_user.primary_org,
        )
    )


@router.get("/users", response_model=UserListResponse)
async def get_user_list(
    page: int = 1,
    size: int = 20,
    keyword: Optional[str] = None,
    orgTag: Optional[str] = None,
    status: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户列表
    
    - 支持分页查询
    - 支持关键词搜索（用户名或邮箱）
    - 支持按组织标签筛选
    - 需要 JWT 认证
    """
    query = select(User)
    
    if keyword:
        query = query.where(
            or_(
                User.username.like(f"%{keyword}%"),
                User.email.like(f"%{keyword}%")
            )
        )
    
    if orgTag:
        query = query.where(
            or_(
                User.org_tags.like(f"%{orgTag}%"),
                User.primary_org == orgTag
            )
        )
    
    count_query = select(func.count(User.id))
    
    if keyword:
        count_query = count_query.where(
            or_(
                User.username.like(f"%{keyword}%"),
                User.email.like(f"%{keyword}%")
            )
        )
    if orgTag:
        count_query = count_query.where(
            or_(
                User.org_tags.like(f"%{orgTag}%"),
                User.primary_org == orgTag
            )
        )
    
    total_result = await db.execute(count_query)
    total_elements = total_result.scalar_one()
    
    offset = (page - 1) * size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(size)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    user_items = []
    for user in users:
        org_tags_list: List[str] = []
        if user.org_tags:
            org_tags_list = [tag.strip() for tag in user.org_tags.split(",") if tag.strip()]
        
        user_items.append(UserListItem(
            userId=user.id,
            username=user.username,
            email=user.email,
            orgTags=org_tags_list,
            primaryOrg=user.primary_org,
            createTime=user.created_at
        ))
    
    total_pages = (total_elements + size - 1) // size if total_elements > 0 else 0
    
    return UserListResponse(
        code=200,
        message="Get users successful",
        data={
            "content": user_items,
            "totalElements": total_elements,
            "totalPages": total_pages,
            "size": size,
            "number": page - 1
        }
    )
