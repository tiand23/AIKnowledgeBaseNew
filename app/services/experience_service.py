"""
结构化经历服务

1) 从文档 chunk 中抽取经历项（项目/期间/角色）。
2) timeline 问题优先使用结构化经历表，按时间排序输出。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import ExperienceItem, FileUpload, DocumentVector
from app.models.user import User, UserRole
from app.services.permission_service import permission_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ExperienceService:

    PERIOD_RE = re.compile(
        r"(?P<sy>20\d{2})\s*[年/\-\.]\s*(?P<sm>\d{1,2})\s*(?:月)?\s*[~～\-—]\s*"
        r"(?:(?P<ey>20\d{2})\s*[年/\-\.]\s*(?P<em>\d{1,2})\s*(?:月)?|(?P<ongoing>現在|今|present|current))",
        re.IGNORECASE
    )
    NAME_RE = re.compile(r"(?:氏名|name)\s*[:：]?\s*([A-Za-z\u3040-\u30ff\u3400-\u9fff]{2,20})")
    ROLE_HINT_RE = re.compile(r"(PM|PL|TL|SE|BSE|PG|担当|役割|ポジション|manager|lead)", re.IGNORECASE)

    @staticmethod
    def _to_ym(year: int, month: int) -> int:
        mm = min(max(int(month), 1), 12)
        return int(year) * 100 + mm

    @staticmethod
    def _extract_person_name(text: str) -> Optional[str]:
        m = ExperienceService.NAME_RE.search(text or "")
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _pick_project_name(window: str) -> str:
        text = re.sub(r"\s+", " ", window or "").strip()
        m = re.search(
            r"([A-Za-z0-9\u3040-\u30ff\u3400-\u9fff・\-\(\)（）]{3,80}"
            r"(?:システム|系统|System|APP|App|プロジェクト|项目|案件))",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()[:255]

        cand = re.sub(r"[;|]+", " ", text).strip()
        return cand[:80] if cand else "未命名项目"

    @staticmethod
    def _pick_role_summary(window: str) -> Optional[str]:
        text = re.sub(r"\s+", " ", window or "").strip()
        m = re.search(
            r"(PM|PL|TL|SE|BSE|PG|担当|役割|ポジション)[^。;\n]{0,120}",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(0).strip()[:255]
        return None

    def extract_experience_items(
        self,
        chunks: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """
        从切块文本中抽取经历项（通用规则）。
        """
        person_name: Optional[str] = None
        items: List[Dict[str, Any]] = []
        now = datetime.now()
        now_ym = self._to_ym(now.year, now.month)

        for chunk in chunks:
            chunk_text = str(chunk.get("text") or "")
            if not chunk_text:
                continue

            if not person_name:
                person_name = self._extract_person_name(chunk_text)

            for m in self.PERIOD_RE.finditer(chunk_text):
                sy = int(m.group("sy"))
                sm = int(m.group("sm"))
                start_ym = self._to_ym(sy, sm)

                if m.group("ongoing"):
                    end_ym = now_ym
                else:
                    ey = int(m.group("ey"))
                    em = int(m.group("em"))
                    end_ym = self._to_ym(ey, em)

                tail = chunk_text[m.end(): m.end() + 240]
                head = chunk_text[max(0, m.start() - 80): m.start()]
                window = f"{head} {tail}"

                project_name = self._pick_project_name(window)
                role_summary = self._pick_role_summary(window)
                period_text = m.group(0)

                items.append(
                    {
                        "project_name": project_name,
                        "role_summary": role_summary,
                        "start_ym": start_ym,
                        "end_ym": end_ym,
                        "period_text": period_text[:64],
                        "source_chunk_id": int(chunk.get("chunk_id", 0) or 0),
                        "evidence_text": window[:500],
                    }
                )

        uniq: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
        for item in items:
            key = (item["project_name"], item["start_ym"], item["end_ym"])
            if key not in uniq:
                uniq[key] = item
        return person_name, list(uniq.values())

    async def rebuild_for_file(
        self,
        db: AsyncSession,
        file_md5: str,
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        重建某文件的经历索引（先删后建）。
        """
        await db.execute(delete(ExperienceItem).where(ExperienceItem.file_md5 == file_md5))
        await db.flush()

        person_name, items = self.extract_experience_items(chunks)
        if not items:
            return {"items": 0}

        rows = [
            ExperienceItem(
                file_md5=file_md5,
                person_name=person_name,
                project_name=item["project_name"],
                role_summary=item["role_summary"],
                start_ym=item["start_ym"],
                end_ym=item["end_ym"],
                period_text=item["period_text"],
                source_chunk_id=item["source_chunk_id"],
                evidence_text=item["evidence_text"],
            )
            for item in items
        ]
        db.add_all(rows)
        await db.flush()
        return {"items": len(rows)}

    @staticmethod
    async def _get_accessible_file_md5_set(
        db: AsyncSession,
        user: User,
        kb_profile: Optional[str] = None,
    ) -> Set[str]:
        if user.role == UserRole.ADMIN:
            stmt = select(FileUpload.file_md5)
            if kb_profile:
                stmt = stmt.where(FileUpload.kb_profile == kb_profile)
            rows = await db.execute(stmt)
            return {x[0] for x in rows.all() if x and x[0]}

        accessible_tags = await permission_service.get_user_accessible_tags(db, user)
        conditions = permission_service.build_db_file_access_conditions(
            user=user,
            accessible_tags=accessible_tags,
        )

        stmt = select(FileUpload.file_md5).where(or_(*conditions))
        if kb_profile:
            stmt = stmt.where(FileUpload.kb_profile == kb_profile)
        rows = await db.execute(stmt)
        return {x[0] for x in rows.all() if x and x[0]}

    async def query_recent_items(
        self,
        db: AsyncSession,
        user: User,
        top_n: int = 3,
        ask_distance: bool = False,
        kb_profile: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        通用 timeline 查询：按结束年月倒序返回最近 N 项。
        """
        accessible_file_md5s = await self._get_accessible_file_md5_set(db, user, kb_profile=kb_profile)
        if not accessible_file_md5s:
            return []

        file_rows = await db.execute(
            select(FileUpload.file_md5, FileUpload.file_name).where(FileUpload.file_md5.in_(accessible_file_md5s))
        )
        file_name_map = {row[0]: row[1] for row in file_rows.all()}

        query_stmt = (
            select(ExperienceItem)
            .where(ExperienceItem.file_md5.in_(accessible_file_md5s))
            .order_by(ExperienceItem.end_ym.desc(), ExperienceItem.start_ym.desc(), ExperienceItem.id.desc())
        )
        query_stmt = query_stmt.limit(max(1, min(top_n, 20)))
        rows = await db.execute(query_stmt)
        items = rows.scalars().all()
        if not items:
            await self._backfill_from_vectors(db, accessible_file_md5s)
            rows = await db.execute(query_stmt)
            items = rows.scalars().all()
        if not items:
            return []

        now = datetime.now()
        now_ym = now.year * 12 + now.month
        results: List[Dict[str, Any]] = []
        for item in items:
            period = item.period_text or ""
            role = item.role_summary or "未明确角色"
            text = (
                f"[时间线] 项目: {item.project_name} ; 期间: {period} ; 角色: {role}"
            )
            if ask_distance and item.end_ym:
                ey = int(item.end_ym // 100)
                em = int(item.end_ym % 100)
                diff = now_ym - (ey * 12 + em)
                text += f" ; 距今天约: {max(0, diff)} 个月"

            results.append(
                {
                    "file_md5": item.file_md5,
                    "chunk_id": int(item.source_chunk_id or item.id),
                    "text_content": text,
                    "score": 9.0,
                    "file_name": file_name_map.get(item.file_md5, "未知文件"),
                }
            )
        return results

    async def _backfill_from_vectors(self, db: AsyncSession, file_md5s: Set[str]) -> None:
        for file_md5 in file_md5s:
            has_item = await db.execute(
                select(ExperienceItem.id).where(ExperienceItem.file_md5 == file_md5).limit(1)
            )
            if has_item.scalar_one_or_none():
                continue

            vec_rows = await db.execute(
                select(DocumentVector.chunk_id, DocumentVector.text_content)
                .where(DocumentVector.file_md5 == file_md5)
                .order_by(DocumentVector.chunk_id.asc())
            )
            vectors = vec_rows.all()
            if not vectors:
                continue

            chunks = [{"chunk_id": int(r[0]), "text": str(r[1] or "")} for r in vectors]
            person_name, parsed_items = self.extract_experience_items(chunks)
            if not parsed_items:
                continue

            rows = [
                ExperienceItem(
                    file_md5=file_md5,
                    person_name=person_name,
                    project_name=item["project_name"],
                    role_summary=item["role_summary"],
                    start_ym=item["start_ym"],
                    end_ym=item["end_ym"],
                    period_text=item["period_text"],
                    source_chunk_id=item["source_chunk_id"],
                    evidence_text=item["evidence_text"],
                )
                for item in parsed_items
            ]
            db.add_all(rows)
        await db.flush()


experience_service = ExperienceService()
