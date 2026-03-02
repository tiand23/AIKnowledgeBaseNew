#!/usr/bin/env python3
"""
最小端到端冒烟脚本（API级）

用途：
1) 登录
2) 检查场景配置
3) 检查上传列表
4) 执行混合检索（验证检索链路可用）

示例：
  python scripts/e2e_smoke.py --base-url http://localhost:8000 --email you@example.com --password xxx
"""
from __future__ import annotations

import argparse
import sys
from typing import List

import httpx


def _assert_ok(resp: httpx.Response, name: str) -> None:
    if resp.status_code >= 400:
        raise RuntimeError(f"{name} failed: {resp.status_code} {resp.text[:300]}")


def run(base_url: str, email: str, password: str, queries: List[str]) -> None:
    base_url = base_url.rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        login_resp = client.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        _assert_ok(login_resp, "login")
        token = (login_resp.json().get("data") or {}).get("access_token")
        if not token:
            raise RuntimeError("login succeeded but access_token missing")
        headers = {"Authorization": f"Bearer {token}"}
        print("[OK] login")

        profile_resp = client.get(f"{base_url}/api/v1/profile", headers=headers)
        _assert_ok(profile_resp, "profile")
        profile_data = profile_resp.json().get("data") or {}
        print(
            "[OK] profile",
            f"selected={profile_data.get('selected_profile')}",
            f"locked={profile_data.get('locked')}",
        )

        uploads_resp = client.get(f"{base_url}/api/v1/documents/uploads", headers=headers)
        _assert_ok(uploads_resp, "documents/uploads")
        uploads = uploads_resp.json().get("data") or []
        print(f"[OK] uploads count={len(uploads)}")

        for q in queries:
            search_resp = client.get(
                f"{base_url}/api/v1/search/hybrid",
                params={"query": q, "topK": 5},
                headers=headers,
            )
            _assert_ok(search_resp, f"hybrid:{q}")
            rows = search_resp.json().get("data") or []
            print(f"[OK] hybrid query='{q}' hits={len(rows)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="API E2E smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="query text for /search/hybrid (can specify multiple)",
    )
    args = parser.parse_args()

    queries = args.query or [
        "田地さんの強みは？",
        "直近3件のプロジェクト",
        "このDB項目変更の影響範囲は？",
    ]

    try:
        run(
            base_url=args.base_url,
            email=args.email,
            password=args.password,
            queries=queries,
        )
        print("[DONE] smoke test passed")
        return 0
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
