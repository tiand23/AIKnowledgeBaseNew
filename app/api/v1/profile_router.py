"""
知识库场景配置接口
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.profile import (
    IntentKeywordsConfigResponse,
    IntentKeywordsUpdateRequest,
    IntentKeywordsUpdateResponse,
    ProfileStateData,
    ProfileStateResponse,
    ProfileSelectRequest,
    ProfileSelectResponse,
    ProfileOption,
)
from app.services.intent_keyword_config_service import intent_keyword_config_service
from app.services.profile_service import profile_service


router = APIRouter()


@router.get("/profile", response_model=ProfileStateResponse)
async def get_profile_state(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    selected = await profile_service.get_selected_profile(db)
    strategy = profile_service.get_strategy(selected)
    options = [ProfileOption(**item) for item in profile_service.list_profile_options()]
    return ProfileStateResponse(
        code=200,
        message="获取场景配置成功",
        data=ProfileStateData(
            selected_profile=selected,
            selected_name=strategy.name if selected else None,
            locked=bool(selected),
            options=options,
        ),
    )


@router.post("/profile/select", response_model=ProfileSelectResponse)
async def select_profile(
    request: ProfileSelectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    selected = await profile_service.select_profile_once(db, request.profile_id)
    strategy = profile_service.get_strategy(selected)
    options = [ProfileOption(**item) for item in profile_service.list_profile_options()]
    return ProfileSelectResponse(
        code=200,
        message="场景配置已保存",
        data=ProfileStateData(
            selected_profile=selected,
            selected_name=strategy.name,
            locked=True,
            options=options,
        ),
    )


@router.get("/profile/intent-keywords", response_model=IntentKeywordsConfigResponse)
async def get_intent_keywords_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    data = await intent_keyword_config_service.get_config(db)
    return IntentKeywordsConfigResponse(
        code=200,
        message="意图关键词配置获取成功",
        data=data,
    )


@router.put("/profile/intent-keywords", response_model=IntentKeywordsUpdateResponse)
async def update_intent_keywords_config(
    request: IntentKeywordsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    payload = {item.key: list(item.keywords or []) for item in request.categories}
    data = await intent_keyword_config_service.update_config(db, payload)
    return IntentKeywordsUpdateResponse(
        code=200,
        message="意图关键词配置已保存",
        data=data,
    )
