"""
評価 Schema
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import BaseResponse


class EvalRunCreateRequest(BaseModel):
    runName: str = Field(..., min_length=1, max_length=128)
    gitCommit: Optional[str] = Field(None, max_length=64)
    env: Optional[str] = Field(None, max_length=32)


class EvalRunData(BaseModel):
    runId: int
    runName: str
    gitCommit: Optional[str] = None
    env: Optional[str] = None
    status: str
    startedAt: datetime
    finishedAt: Optional[datetime] = None
    createdBy: Optional[int] = None


class EvalRunCreateResponse(BaseResponse[EvalRunData]):
    code: int = Field(200, description="ステータスコード")
    message: str = Field("評価Runを作成しました", description="メッセージ")


class EvalMetricItem(BaseModel):
    metricKey: str = Field(..., min_length=1, max_length=64)
    metricValue: float
    threshold: Optional[float] = None
    passed: Optional[bool] = None
    dimension: Optional[str] = Field(None, max_length=64)
    note: Optional[str] = None


class EvalMetricsUpsertRequest(BaseModel):
    items: List[EvalMetricItem] = Field(default_factory=list)


class EvalCaseItem(BaseModel):
    caseId: str = Field(..., min_length=1, max_length=64)
    category: Optional[str] = Field(None, max_length=64)
    query: str
    expected: Optional[str] = None
    predicted: Optional[str] = None
    score: Optional[float] = None
    passed: bool = False
    latencyMs: Optional[int] = None


class EvalCasesUpsertRequest(BaseModel):
    items: List[EvalCaseItem] = Field(default_factory=list)


class EvalEvidenceItem(BaseModel):
    caseId: str = Field(..., min_length=1, max_length=64)
    fileMd5: Optional[str] = Field(None, max_length=32)
    chunkId: Optional[int] = None
    imagePath: Optional[str] = Field(None, max_length=255)
    evidenceText: Optional[str] = None
    score: Optional[float] = None
    isCorrectEvidence: Optional[bool] = None


class EvalEvidencesUpsertRequest(BaseModel):
    items: List[EvalEvidenceItem] = Field(default_factory=list)


class EvalAssetCoverageItem(BaseModel):
    assetType: str = Field(..., min_length=1, max_length=32)
    totalCount: int = Field(0, ge=0)
    indexedCount: int = Field(0, ge=0)
    coverageRate: Optional[float] = Field(None, ge=0.0, le=1.0)
    note: Optional[str] = None


class EvalAssetCoverageUpsertRequest(BaseModel):
    items: List[EvalAssetCoverageItem] = Field(default_factory=list)


class EvalRunFinishRequest(BaseModel):
    status: str = Field("done", pattern="^(done|failed)$")


class EvalBulkUpsertData(BaseModel):
    affected: int = 0


class EvalBulkUpsertResponse(BaseResponse[EvalBulkUpsertData]):
    code: int = Field(200, description="ステータスコード")
    message: str = Field("保存しました", description="メッセージ")


class EvalRunSummaryData(BaseModel):
    run: EvalRunData
    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    coverage: List[Dict[str, Any]] = Field(default_factory=list)
    caseStats: Dict[str, Any] = Field(default_factory=dict)


class EvalRunSummaryResponse(BaseResponse[EvalRunSummaryData]):
    code: int = Field(200, description="ステータスコード")
    message: str = Field("評価詳細を取得しました", description="メッセージ")


class EvalRunListItem(BaseModel):
    runId: int
    runName: str
    gitCommit: Optional[str] = None
    env: Optional[str] = None
    status: str
    startedAt: datetime
    finishedAt: Optional[datetime] = None
    metricsCount: int = 0
    casesCount: int = 0
    coverageCount: int = 0


class EvalRunListResponse(BaseResponse[List[EvalRunListItem]]):
    code: int = Field(200, description="ステータスコード")
    message: str = Field("評価Run一覧を取得しました", description="メッセージ")


class EvalOnlineIntentStat(BaseModel):
    intent: str
    count: int


class EvalOnlineDailyStat(BaseModel):
    date: str
    total: int
    success: int
    noEvidence: int
    error: int
    avgLatencyMs: float


class EvalOnlineQuestionSample(BaseModel):
    createdAt: datetime
    status: str
    intent: Optional[str] = None
    question: str
    answer: Optional[str] = None


class EvalOnlineSummaryData(BaseModel):
    windowStart: datetime
    windowEnd: datetime
    totalQuestions: int
    successCount: int
    noEvidenceCount: int
    errorCount: int
    archivedCount: int
    avgLatencyMs: float
    p95LatencyMs: float
    retrievalHitRate: float
    withSourcesRate: float
    intentStats: List[EvalOnlineIntentStat] = Field(default_factory=list)
    dailyStats: List[EvalOnlineDailyStat] = Field(default_factory=list)
    questionSamples: List[EvalOnlineQuestionSample] = Field(default_factory=list)


class EvalOnlineSummaryResponse(BaseResponse[EvalOnlineSummaryData]):
    code: int = Field(200, description="ステータスコード")
    message: str = Field("オンライン評価を取得しました", description="メッセージ")
