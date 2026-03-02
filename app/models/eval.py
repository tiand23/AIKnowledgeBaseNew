"""
评估体系数据模型
"""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Float,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.models.base import Base, BIGINT_TYPE


class EvalRun(Base):

    __tablename__ = "eval_runs"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    run_name = Column(String(128), nullable=False, comment="运行名称")
    git_commit = Column(String(64), nullable=True, comment="代码版本")
    env = Column(String(32), nullable=True, comment="环境标识")
    status = Column(String(20), nullable=False, default="running", comment="状态")
    started_at = Column(DateTime, nullable=False, server_default=func.now(), comment="开始时间")
    finished_at = Column(DateTime, nullable=True, comment="结束时间")
    created_by = Column(BIGINT_TYPE, nullable=True, comment="创建者用户ID")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    metrics = relationship("EvalMetric", back_populates="run", cascade="all, delete-orphan")
    cases = relationship("EvalCase", back_populates="run", cascade="all, delete-orphan")
    evidences = relationship("EvalEvidence", back_populates="run", cascade="all, delete-orphan")
    asset_coverages = relationship("EvalAssetCoverage", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_eval_runs_status", "status"),
        Index("idx_eval_runs_started_at", "started_at"),
        Index("idx_eval_runs_name", "run_name"),
    )


class EvalMetric(Base):

    __tablename__ = "eval_metrics"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    run_id = Column(
        BIGINT_TYPE,
        ForeignKey("eval_runs.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="关联运行ID",
    )
    metric_key = Column(String(64), nullable=False, comment="指标键")
    metric_value = Column(Float, nullable=False, comment="指标值")
    threshold = Column(Float, nullable=True, comment="阈值")
    passed = Column(Boolean, nullable=True, comment="是否达标")
    dimension = Column(String(64), nullable=True, comment="维度，如layout/flow")
    note = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    run = relationship("EvalRun", back_populates="metrics")

    __table_args__ = (
        Index("idx_eval_metrics_run", "run_id"),
        Index("idx_eval_metrics_key", "metric_key"),
        Index("idx_eval_metrics_dim", "dimension"),
    )


class EvalCase(Base):

    __tablename__ = "eval_cases"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    run_id = Column(
        BIGINT_TYPE,
        ForeignKey("eval_runs.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="关联运行ID",
    )
    case_id = Column(String(64), nullable=False, comment="用例ID")
    category = Column(String(64), nullable=True, comment="分类")
    query = Column(Text, nullable=False, comment="问题")
    expected = Column(Text, nullable=True, comment="期望答案/摘要")
    predicted = Column(Text, nullable=True, comment="模型答案/摘要")
    score = Column(Float, nullable=True, comment="用例分数")
    passed = Column(Boolean, nullable=False, default=False, comment="是否通过")
    latency_ms = Column(Integer, nullable=True, comment="时延")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    run = relationship("EvalRun", back_populates="cases")

    __table_args__ = (
        Index("idx_eval_cases_run", "run_id"),
        Index("idx_eval_cases_category", "category"),
        UniqueConstraint("run_id", "case_id", name="uk_eval_cases_run_case"),
    )


class EvalEvidence(Base):

    __tablename__ = "eval_evidences"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    run_id = Column(
        BIGINT_TYPE,
        ForeignKey("eval_runs.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="关联运行ID",
    )
    case_id = Column(String(64), nullable=False, comment="用例ID")
    file_md5 = Column(String(32), nullable=True, comment="文件MD5")
    chunk_id = Column(Integer, nullable=True, comment="chunk_id")
    image_path = Column(String(255), nullable=True, comment="图片路径")
    evidence_text = Column(Text, nullable=True, comment="证据文本摘要")
    score = Column(Float, nullable=True, comment="证据分")
    is_correct_evidence = Column(Boolean, nullable=True, comment="是否正确证据")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    run = relationship("EvalRun", back_populates="evidences")

    __table_args__ = (
        Index("idx_eval_evidences_run", "run_id"),
        Index("idx_eval_evidences_case", "case_id"),
        Index("idx_eval_evidences_file_chunk", "file_md5", "chunk_id"),
    )


class EvalAssetCoverage(Base):

    __tablename__ = "eval_asset_coverages"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    run_id = Column(
        BIGINT_TYPE,
        ForeignKey("eval_runs.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="关联运行ID",
    )
    asset_type = Column(String(32), nullable=False, comment="资产类型，如file/chunk/image")
    total_count = Column(Integer, nullable=False, default=0, comment="总量")
    indexed_count = Column(Integer, nullable=False, default=0, comment="已覆盖数量")
    coverage_rate = Column(Float, nullable=False, default=0.0, comment="覆盖率")
    note = Column(Text, nullable=True, comment="说明")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    run = relationship("EvalRun", back_populates="asset_coverages")

    __table_args__ = (
        Index("idx_eval_asset_cov_run", "run_id"),
        UniqueConstraint("run_id", "asset_type", name="uk_eval_asset_cov_run_asset"),
    )
