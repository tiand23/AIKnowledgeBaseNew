"""
评估体系服务
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.eval import EvalRun, EvalMetric, EvalCase, EvalEvidence, EvalAssetCoverage
from app.models.chat import ChatUsageEvent


class EvalService:

    @staticmethod
    def _to_run_data(run: EvalRun) -> Dict[str, Any]:
        return {
            "runId": int(run.id),
            "runName": run.run_name,
            "gitCommit": run.git_commit,
            "env": run.env,
            "status": run.status,
            "startedAt": run.started_at,
            "finishedAt": run.finished_at,
            "createdBy": run.created_by,
        }

    async def create_run(
        self,
        db: AsyncSession,
        run_name: str,
        created_by: Optional[int] = None,
        git_commit: Optional[str] = None,
        env: Optional[str] = None,
    ) -> EvalRun:
        run = EvalRun(
            run_name=run_name,
            git_commit=git_commit,
            env=env,
            status="running",
            created_by=created_by,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    async def get_run(self, db: AsyncSession, run_id: int) -> EvalRun | None:
        result = await db.execute(select(EvalRun).where(EvalRun.id == run_id))
        return result.scalar_one_or_none()

    async def finish_run(self, db: AsyncSession, run_id: int, status: str) -> EvalRun | None:
        result = await db.execute(select(EvalRun).where(EvalRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return None
        run.status = status
        run.finished_at = datetime.utcnow()
        await db.commit()
        await db.refresh(run)
        return run

    async def upsert_metrics(self, db: AsyncSession, run_id: int, items: List[Dict[str, Any]]) -> int:
        await db.execute(delete(EvalMetric).where(EvalMetric.run_id == run_id))
        for item in items:
            db.add(
                EvalMetric(
                    run_id=run_id,
                    metric_key=str(item.get("metricKey") or "").strip(),
                    metric_value=float(item.get("metricValue") or 0.0),
                    threshold=(float(item["threshold"]) if item.get("threshold") is not None else None),
                    passed=item.get("passed"),
                    dimension=(str(item.get("dimension") or "").strip() or None),
                    note=item.get("note"),
                )
            )
        await db.commit()
        return len(items)

    async def upsert_cases(self, db: AsyncSession, run_id: int, items: List[Dict[str, Any]]) -> int:
        await db.execute(delete(EvalCase).where(EvalCase.run_id == run_id))
        for item in items:
            db.add(
                EvalCase(
                    run_id=run_id,
                    case_id=str(item.get("caseId") or "").strip(),
                    category=(str(item.get("category") or "").strip() or None),
                    query=str(item.get("query") or ""),
                    expected=item.get("expected"),
                    predicted=item.get("predicted"),
                    score=(float(item["score"]) if item.get("score") is not None else None),
                    passed=bool(item.get("passed")),
                    latency_ms=(int(item["latencyMs"]) if item.get("latencyMs") is not None else None),
                )
            )
        await db.commit()
        return len(items)

    async def replace_evidences(self, db: AsyncSession, run_id: int, items: List[Dict[str, Any]]) -> int:
        await db.execute(delete(EvalEvidence).where(EvalEvidence.run_id == run_id))
        for item in items:
            db.add(
                EvalEvidence(
                    run_id=run_id,
                    case_id=str(item.get("caseId") or "").strip(),
                    file_md5=(str(item.get("fileMd5") or "").strip() or None),
                    chunk_id=(int(item["chunkId"]) if item.get("chunkId") is not None else None),
                    image_path=(str(item.get("imagePath") or "").strip() or None),
                    evidence_text=item.get("evidenceText"),
                    score=(float(item["score"]) if item.get("score") is not None else None),
                    is_correct_evidence=item.get("isCorrectEvidence"),
                )
            )
        await db.commit()
        return len(items)

    async def upsert_asset_coverage(self, db: AsyncSession, run_id: int, items: List[Dict[str, Any]]) -> int:
        await db.execute(delete(EvalAssetCoverage).where(EvalAssetCoverage.run_id == run_id))
        for item in items:
            total = int(item.get("totalCount") or 0)
            indexed = int(item.get("indexedCount") or 0)
            rate = item.get("coverageRate")
            if rate is None:
                rate = (float(indexed) / float(total)) if total > 0 else 0.0
            db.add(
                EvalAssetCoverage(
                    run_id=run_id,
                    asset_type=str(item.get("assetType") or "").strip(),
                    total_count=total,
                    indexed_count=indexed,
                    coverage_rate=float(rate),
                    note=item.get("note"),
                )
            )
        await db.commit()
        return len(items)

    async def list_runs(self, db: AsyncSession, limit: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        stmt = select(EvalRun).order_by(EvalRun.id.desc()).limit(limit)
        if status:
            stmt = stmt.where(EvalRun.status == status)
        rows = (await db.execute(stmt)).scalars().all()
        result: List[Dict[str, Any]] = []
        for run in rows:
            metrics_count = (
                await db.execute(select(func.count(EvalMetric.id)).where(EvalMetric.run_id == run.id))
            ).scalar_one()
            cases_count = (
                await db.execute(select(func.count(EvalCase.id)).where(EvalCase.run_id == run.id))
            ).scalar_one()
            coverage_count = (
                await db.execute(select(func.count(EvalAssetCoverage.id)).where(EvalAssetCoverage.run_id == run.id))
            ).scalar_one()
            result.append(
                {
                    "runId": int(run.id),
                    "runName": run.run_name,
                    "gitCommit": run.git_commit,
                    "env": run.env,
                    "status": run.status,
                    "startedAt": run.started_at,
                    "finishedAt": run.finished_at,
                    "metricsCount": int(metrics_count or 0),
                    "casesCount": int(cases_count or 0),
                    "coverageCount": int(coverage_count or 0),
                }
            )
        return result

    async def get_run_summary(self, db: AsyncSession, run_id: int) -> Optional[Dict[str, Any]]:
        run_result = await db.execute(select(EvalRun).where(EvalRun.id == run_id))
        run = run_result.scalar_one_or_none()
        if not run:
            return None

        metrics = (
            await db.execute(
                select(EvalMetric).where(EvalMetric.run_id == run_id).order_by(EvalMetric.id.asc())
            )
        ).scalars().all()
        coverage = (
            await db.execute(
                select(EvalAssetCoverage).where(EvalAssetCoverage.run_id == run_id).order_by(EvalAssetCoverage.id.asc())
            )
        ).scalars().all()
        total_cases = (
            await db.execute(select(func.count(EvalCase.id)).where(EvalCase.run_id == run_id))
        ).scalar_one()
        passed_cases = (
            await db.execute(
                select(func.count(EvalCase.id)).where(EvalCase.run_id == run_id, EvalCase.passed.is_(True))
            )
        ).scalar_one()

        case_total = int(total_cases or 0)
        case_passed = int(passed_cases or 0)
        pass_rate = (float(case_passed) / float(case_total)) if case_total > 0 else 0.0

        return {
            "run": self._to_run_data(run),
            "metrics": [
                {
                    "metricKey": m.metric_key,
                    "metricValue": m.metric_value,
                    "threshold": m.threshold,
                    "passed": m.passed,
                    "dimension": m.dimension,
                    "note": m.note,
                }
                for m in metrics
            ],
            "coverage": [
                {
                    "assetType": c.asset_type,
                    "totalCount": c.total_count,
                    "indexedCount": c.indexed_count,
                    "coverageRate": c.coverage_rate,
                    "note": c.note,
                }
                for c in coverage
            ],
            "caseStats": {
                "total": case_total,
                "passed": case_passed,
                "passRate": pass_rate,
            },
        }

    @staticmethod
    def _calc_p95(values: List[int]) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = max(0, min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95) - 1))
        return float(sorted_vals[idx])

    async def get_online_summary(
        self,
        db: AsyncSession,
        *,
        days: int = 7,
        profile: Optional[str] = None,
        user_id: Optional[int] = None,
        sample_limit: int = 20,
    ) -> Dict[str, Any]:
        now = datetime.utcnow()
        window_start = now - timedelta(days=max(1, int(days or 1)))

        stmt = select(ChatUsageEvent).where(ChatUsageEvent.created_at >= window_start)
        if profile:
            stmt = stmt.where(ChatUsageEvent.selected_profile == profile)
        if user_id is not None:
            stmt = stmt.where(ChatUsageEvent.user_id == int(user_id))

        rows = (await db.execute(stmt.order_by(ChatUsageEvent.created_at.asc()))).scalars().all()

        total = len(rows)
        status_counter: Counter[str] = Counter(str(r.status or "unknown") for r in rows)
        success_count = int(status_counter.get("success", 0))
        no_evidence_count = int(status_counter.get("no_evidence", 0))
        error_count = int(status_counter.get("error", 0))
        archived_count = int(status_counter.get("archived", 0))

        latencies = [int(r.latency_ms) for r in rows if r.latency_ms is not None]
        avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
        p95_latency = self._calc_p95(latencies)

        retrieval_hit_count = sum(1 for r in rows if int(r.retrieval_count or 0) > 0)
        with_sources_count = sum(1 for r in rows if int(r.source_count or 0) > 0)
        retrieval_hit_rate = (float(retrieval_hit_count) / float(total)) if total > 0 else 0.0
        with_sources_rate = (float(with_sources_count) / float(total)) if total > 0 else 0.0

        intent_counter: Counter[str] = Counter()
        for r in rows:
            key = str(r.intent or "unknown").strip() or "unknown"
            intent_counter[key] += 1
        intent_stats = [{"intent": k, "count": int(v)} for k, v in intent_counter.most_common(12)]

        daily_bucket: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "success": 0, "no_evidence": 0, "error": 0, "latencies": []}
        )
        for r in rows:
            day = str((r.created_at or now).date())
            item = daily_bucket[day]
            item["total"] += 1
            st = str(r.status or "")
            if st == "success":
                item["success"] += 1
            elif st == "no_evidence":
                item["no_evidence"] += 1
            elif st == "error":
                item["error"] += 1
            if r.latency_ms is not None:
                item["latencies"].append(int(r.latency_ms))
        daily_stats = []
        for d in sorted(daily_bucket.keys()):
            item = daily_bucket[d]
            ls = item["latencies"]
            daily_stats.append(
                {
                    "date": d,
                    "total": int(item["total"]),
                    "success": int(item["success"]),
                    "noEvidence": int(item["no_evidence"]),
                    "error": int(item["error"]),
                    "avgLatencyMs": float(sum(ls) / len(ls)) if ls else 0.0,
                }
            )

        sample_rows = sorted(
            [r for r in rows if str(r.status or "") in {"no_evidence", "error"}],
            key=lambda x: x.created_at or now,
            reverse=True,
        )[: max(1, int(sample_limit or 20))]
        question_samples = [
            {
                "createdAt": r.created_at,
                "status": str(r.status or ""),
                "intent": r.intent,
                "question": r.question_text or "",
                "answer": r.answer_text or "",
            }
            for r in sample_rows
        ]

        return {
            "windowStart": window_start,
            "windowEnd": now,
            "totalQuestions": total,
            "successCount": success_count,
            "noEvidenceCount": no_evidence_count,
            "errorCount": error_count,
            "archivedCount": archived_count,
            "avgLatencyMs": float(avg_latency),
            "p95LatencyMs": float(p95_latency),
            "retrievalHitRate": float(retrieval_hit_rate),
            "withSourcesRate": float(with_sources_rate),
            "intentStats": intent_stats,
            "dailyStats": daily_stats,
            "questionSamples": question_samples,
        }


eval_service = EvalService()
