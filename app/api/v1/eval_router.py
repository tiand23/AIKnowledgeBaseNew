"""
評価インターフェース
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.models.user import User, UserRole
from app.schemas.eval import (
    EvalRunCreateRequest,
    EvalRunCreateResponse,
    EvalRunData,
    EvalMetricsUpsertRequest,
    EvalCasesUpsertRequest,
    EvalEvidencesUpsertRequest,
    EvalAssetCoverageUpsertRequest,
    EvalBulkUpsertResponse,
    EvalBulkUpsertData,
    EvalRunFinishRequest,
    EvalRunSummaryResponse,
    EvalRunListResponse,
    EvalOnlineSummaryResponse,
)
from app.services.eval_service import eval_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限",
        )


async def _ensure_run_exists(db: AsyncSession, run_id: int) -> None:
    run = await eval_service.get_run(db=db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="評価Runが存在しません")


@router.post("/runs", response_model=EvalRunCreateResponse)
async def create_eval_run(
    payload: EvalRunCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    run = await eval_service.create_run(
        db=db,
        run_name=payload.runName.strip(),
        created_by=int(current_user.id),
        git_commit=(payload.gitCommit or None),
        env=(payload.env or None),
    )
    return EvalRunCreateResponse(
        code=200,
        message="評価Runを作成しました",
        data=EvalRunData(
            runId=int(run.id),
            runName=run.run_name,
            gitCommit=run.git_commit,
            env=run.env,
            status=run.status,
            startedAt=run.started_at,
            finishedAt=run.finished_at,
            createdBy=run.created_by,
        ),
    )


@router.post("/runs/{run_id}/metrics", response_model=EvalBulkUpsertResponse)
async def upsert_eval_metrics(
    run_id: int,
    payload: EvalMetricsUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    await _ensure_run_exists(db=db, run_id=run_id)
    affected = await eval_service.upsert_metrics(db=db, run_id=run_id, items=[x.model_dump() for x in payload.items])
    return EvalBulkUpsertResponse(code=200, message="評価指標を保存しました", data=EvalBulkUpsertData(affected=affected))


@router.post("/runs/{run_id}/cases", response_model=EvalBulkUpsertResponse)
async def upsert_eval_cases(
    run_id: int,
    payload: EvalCasesUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    await _ensure_run_exists(db=db, run_id=run_id)
    affected = await eval_service.upsert_cases(db=db, run_id=run_id, items=[x.model_dump() for x in payload.items])
    return EvalBulkUpsertResponse(code=200, message="評価ケースを保存しました", data=EvalBulkUpsertData(affected=affected))


@router.post("/runs/{run_id}/evidences", response_model=EvalBulkUpsertResponse)
async def replace_eval_evidences(
    run_id: int,
    payload: EvalEvidencesUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    await _ensure_run_exists(db=db, run_id=run_id)
    affected = await eval_service.replace_evidences(db=db, run_id=run_id, items=[x.model_dump() for x in payload.items])
    return EvalBulkUpsertResponse(code=200, message="評価エビデンスを保存しました", data=EvalBulkUpsertData(affected=affected))


@router.post("/runs/{run_id}/asset-coverage", response_model=EvalBulkUpsertResponse)
async def upsert_eval_asset_coverage(
    run_id: int,
    payload: EvalAssetCoverageUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    await _ensure_run_exists(db=db, run_id=run_id)
    affected = await eval_service.upsert_asset_coverage(db=db, run_id=run_id, items=[x.model_dump() for x in payload.items])
    return EvalBulkUpsertResponse(code=200, message="資産カバレッジを保存しました", data=EvalBulkUpsertData(affected=affected))


@router.post("/runs/{run_id}/finish", response_model=EvalRunCreateResponse)
async def finish_eval_run(
    run_id: int,
    payload: EvalRunFinishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    run = await eval_service.finish_run(db=db, run_id=run_id, status=payload.status)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="評価Runが存在しません")
    return EvalRunCreateResponse(
        code=200,
        message="評価Runの状態を更新しました",
        data=EvalRunData(
            runId=int(run.id),
            runName=run.run_name,
            gitCommit=run.git_commit,
            env=run.env,
            status=run.status,
            startedAt=run.started_at,
            finishedAt=run.finished_at,
            createdBy=run.created_by,
        ),
    )


@router.get("/runs", response_model=EvalRunListResponse)
async def list_eval_runs(
    limit: int = Query(20, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    data = await eval_service.list_runs(db=db, limit=limit, status=status_filter)
    return EvalRunListResponse(code=200, message="評価Run一覧を取得しました", data=data)


@router.get("/runs/{run_id}", response_model=EvalRunSummaryResponse)
async def get_eval_run_summary(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    summary = await eval_service.get_run_summary(db=db, run_id=run_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="評価Runが存在しません")
    return EvalRunSummaryResponse(code=200, message="評価詳細を取得しました", data=summary)


@router.get("/online/summary", response_model=EvalOnlineSummaryResponse)
async def get_online_eval_summary(
    days: int = Query(7, ge=1, le=90, description="集計対象日数"),
    profile: str | None = Query(None, description="任意のシナリオ絞り込み"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scope_user_id = None if current_user.role == UserRole.ADMIN else int(current_user.id)
    data = await eval_service.get_online_summary(
        db=db,
        days=days,
        profile=(profile or None),
        user_id=scope_user_id,
    )
    return EvalOnlineSummaryResponse(code=200, message="オンライン評価を取得しました", data=data)
