#!/usr/bin/env python3
"""
检索离线评测脚本（API 级）

能力：
1) 登录并可选锁定场景 profile
2) 逐条调用 /api/v1/search/{hybrid|flow}
3) 计算 Hit@K / Recall@K / MRR
4) 输出失败样例，便于回归

数据集格式：JSONL（一行一个样例）
{
  "id": "q1",
  "query": "システム構成図を見たい",
  "top_k": 8,
  "expected": {
    "file_md5_any": ["xxxxxxxx"],
    "file_name_any": ["システムイメージ.xlsx"],
    "text_contains_any": ["工番負荷予測"]
  }
}
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class EvalCase:
    case_id: str
    query: str
    top_k: int
    expected: Dict[str, Any]


def _load_jsonl(path: Path) -> List[EvalCase]:
    if not path.exists():
        raise FileNotFoundError(f"dataset not found: {path}")
    rows: List[EvalCase] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            raw = json.loads(s)
            query = str(raw.get("query") or "").strip()
            if not query:
                raise ValueError(f"line {idx}: query is required")
            case_id = str(raw.get("id") or f"line-{idx}")
            top_k = int(raw.get("top_k") or 10)
            expected = raw.get("expected") or {}
            if not isinstance(expected, dict):
                raise ValueError(f"line {idx}: expected must be object")
            rows.append(EvalCase(case_id=case_id, query=query, top_k=top_k, expected=expected))
    if not rows:
        raise ValueError("dataset is empty")
    return rows


def _contains_any(hay: str, needles: List[str]) -> bool:
    if not needles:
        return False
    h = hay.lower()
    return any(str(n).lower() in h for n in needles if str(n).strip())


def _is_relevant(hit: Dict[str, Any], expected: Dict[str, Any]) -> bool:
    file_md5_any = [str(x) for x in (expected.get("file_md5_any") or [])]
    file_name_any = [str(x) for x in (expected.get("file_name_any") or [])]
    text_contains_any = [str(x) for x in (expected.get("text_contains_any") or [])]
    min_score = expected.get("min_score")

    if not (file_md5_any or file_name_any or text_contains_any or min_score is not None):
        return False

    file_md5 = str(hit.get("file_md5") or "")
    file_name = str(hit.get("file_name") or "")
    text = str(hit.get("text_content") or "")
    score = float(hit.get("score") or 0.0)

    conds: List[bool] = []
    if file_md5_any:
        conds.append(file_md5 in file_md5_any)
    if file_name_any:
        conds.append(_contains_any(file_name, file_name_any))
    if text_contains_any:
        conds.append(_contains_any(text, text_contains_any))
    if min_score is not None:
        try:
            conds.append(score >= float(min_score))
        except Exception:
            conds.append(False)
    return any(conds)


def _assert_ok(resp: httpx.Response, name: str) -> None:
    if resp.status_code >= 400:
        raise RuntimeError(f"{name} failed: {resp.status_code} {resp.text[:300]}")


def _extract_token(resp_json: Dict[str, Any]) -> str:
    data = resp_json.get("data") or {}
    return str(data.get("access_token") or resp_json.get("access_token") or "").strip()


def _login(client: httpx.Client, base_url: str, account: str, password: str) -> str:
    login_url = f"{base_url}/api/v1/auth/login"
    attempts = [
        ("json:email", {"json": {"email": account, "password": password}}),
        ("json:username", {"json": {"username": account, "password": password}}),
        (
            "form:oauth2",
            {
                "data": {
                    "username": account,
                    "password": password,
                    "grant_type": "password",
                }
            },
        ),
    ]
    last_error = "unknown"
    for mode, payload in attempts:
        try:
            resp = client.post(login_url, **payload)
            if resp.status_code >= 400:
                last_error = f"{mode}: {resp.status_code} {resp.text[:180]}"
                continue
            token = _extract_token(resp.json())
            if token:
                return token
            last_error = f"{mode}: token missing"
        except Exception as e:
            last_error = f"{mode}: {e}"
    raise RuntimeError(f"login failed (all modes) -> {last_error}")


def _maybe_select_profile(
    client: httpx.Client, base_url: str, headers: Dict[str, str], profile_id: Optional[str]
) -> None:
    if not profile_id:
        return
    state = client.get(f"{base_url}/api/v1/profile", headers=headers)
    _assert_ok(state, "profile:get")
    data = state.json().get("data") or {}
    selected = data.get("selected_profile")
    locked = bool(data.get("locked"))
    if locked and selected != profile_id:
        raise RuntimeError(f"profile locked as '{selected}', cannot switch to '{profile_id}'")
    if selected == profile_id:
        return
    resp = client.post(
        f"{base_url}/api/v1/profile/select",
        headers=headers,
        json={"profile_id": profile_id},
    )
    _assert_ok(resp, "profile:select")


def run_eval(
    base_url: str,
    account: str,
    password: str,
    dataset: Path,
    endpoint: str,
    top_k: int,
    profile_id: Optional[str],
) -> Dict[str, Any]:
    base_url = base_url.rstrip("/")
    cases = _load_jsonl(dataset)
    report_rows: List[Dict[str, Any]] = []
    with httpx.Client(timeout=45.0) as client:
        token = _login(client, base_url, account, password)
        headers = {"Authorization": f"Bearer {token}"}
        _maybe_select_profile(client, base_url, headers, profile_id)

        ep = "flow" if endpoint == "flow" else "hybrid"
        for case in cases:
            k = int(case.top_k or top_k)
            resp = client.get(
                f"{base_url}/api/v1/search/{ep}",
                params={"query": case.query, "topK": k},
                headers=headers,
            )
            _assert_ok(resp, f"search:{case.case_id}")
            hits = resp.json().get("data") or []

            first_rel_rank = None
            rel_count = 0
            for idx, h in enumerate(hits, 1):
                if _is_relevant(h, case.expected):
                    rel_count += 1
                    if first_rel_rank is None:
                        first_rel_rank = idx

            row = {
                "id": case.case_id,
                "query": case.query,
                "k": k,
                "hit_at_k": first_rel_rank is not None,
                "first_rel_rank": first_rel_rank,
                "recall_at_k": 1.0 if rel_count > 0 else 0.0,
                "mrr": (1.0 / float(first_rel_rank)) if first_rel_rank else 0.0,
                "retrieved": len(hits),
                "relevant_in_topk": rel_count,
                "top_hits": [
                    {
                        "rank": i + 1,
                        "file_name": x.get("file_name"),
                        "file_md5": x.get("file_md5"),
                        "score": x.get("score"),
                        "text_preview": str(x.get("text_content") or "")[:120],
                    }
                    for i, x in enumerate(hits[: min(k, 5)])
                ],
            }
            report_rows.append(row)

    total = len(report_rows)
    hit_at_k = sum(1 for r in report_rows if r["hit_at_k"]) / float(total)
    recall_at_k = sum(float(r["recall_at_k"]) for r in report_rows) / float(total)
    mrr = sum(float(r["mrr"]) for r in report_rows) / float(total)
    first_rank_values = [r["first_rel_rank"] for r in report_rows if r["first_rel_rank"] is not None]
    report = {
        "summary": {
            "dataset": str(dataset),
            "endpoint": ep,
            "cases": total,
            "hit_at_k": round(hit_at_k, 4),
            "recall_at_k": round(recall_at_k, 4),
            "mrr": round(mrr, 4),
            "first_rel_rank_avg": round(statistics.mean(first_rank_values), 4) if first_rank_values else None,
        },
        "failures": [r for r in report_rows if not r["hit_at_k"]],
        "rows": report_rows,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieval offline evaluator")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", required=False, help="deprecated: use --account")
    parser.add_argument("--account", required=False, help="login account (email/username)")
    parser.add_argument("--password", required=True)
    parser.add_argument("--dataset", required=True, help="jsonl dataset path")
    parser.add_argument("--endpoint", choices=["hybrid", "flow"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--profile-id", default=None, help="optional, e.g. design")
    parser.add_argument("--out", default=None, help="output report json path")
    args = parser.parse_args()
    account = (args.account or args.email or "").strip()
    if not account:
        print("[FAIL] --account is required (or provide --email)", file=sys.stderr)
        return 1

    try:
        report = run_eval(
            base_url=args.base_url,
            account=account,
            password=args.password,
            dataset=Path(args.dataset),
            endpoint=args.endpoint,
            top_k=int(args.top_k),
            profile_id=args.profile_id,
        )
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print(f"failures={len(report['failures'])}")
        if report["failures"]:
            print("---- failed cases ----")
            for f in report["failures"][:20]:
                print(f"[{f['id']}] {f['query']}")
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"report saved: {out}")
        return 0
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
