"""
PoC: verify whether AI Studio API key can generate image embeddings via Gemini.

Usage:
  export GEMINI_API_KEY="..."
  python scripts/test_gemini_multimodal_embedding.py --image /abs/path/to/image.png

Optional:
  python scripts/test_gemini_multimodal_embedding.py \
    --image /abs/path/to/image.png \
    --model gemini-embedding-2-preview \
    --api-key <KEY> \
    --dimensions 3072
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Gemini multimodal embedding via AI Studio API key")
    parser.add_argument("--image", required=True, help="Absolute path to a PNG/JPEG image")
    parser.add_argument("--api-key", default=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"), help="AI Studio API key")
    parser.add_argument("--model", default=os.getenv("GEMINI_MULTIMODAL_EMBED_MODEL", "gemini-embedding-2-preview"), help="Model name to test")
    parser.add_argument("--dimensions", type=int, default=None, help="Optional output dimension")
    return parser.parse_args()


def _guess_mime_type(image_path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(image_path))
    if guessed and guessed.startswith("image/"):
        return guessed
    return "image/png"


def main() -> int:
    args = _parse_args()
    if not args.api_key:
        print("[ERROR] GEMINI_API_KEY / GOOGLE_API_KEY is not set.")
        return 2

    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists() or not image_path.is_file():
        print(f"[ERROR] Image not found: {image_path}")
        return 2

    payload = {
        "model": f"models/{args.model}",
        "content": {
            "parts": [
                {
                    "inline_data": {
                        "mime_type": _guess_mime_type(image_path),
                        "data": base64.b64encode(image_path.read_bytes()).decode("utf-8"),
                    }
                }
            ]
        },
    }
    if args.dimensions:
        payload["outputDimensionality"] = args.dimensions

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{args.model}:embedContent?{urlencode({'key': args.api_key})}"
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print("=" * 72)
    print("Gemini AI Studio multimodal embedding PoC")
    print("=" * 72)
    print(f"image     : {image_path}")
    print(f"model     : {args.model}")
    print(f"api key   : {args.api_key[:8]}...")
    print(f"dimensions: {args.dimensions if args.dimensions else 'default'}")

    try:
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        print("[FAILED] Gemini multimodal embedding call failed.")
        print(f"type   : HTTPError")
        print(f"detail : status={e.code}, body={detail[:800]}")
        return 1
    except URLError as e:
        print("[FAILED] Gemini multimodal embedding call failed.")
        print(f"type   : URLError")
        print(f"detail : {e}")
        return 1
    except Exception as e:
        print("[FAILED] Gemini multimodal embedding call failed.")
        print(f"type   : {type(e).__name__}")
        print(f"detail : {e}")
        return 1

    data = json.loads(body)
    values = []
    if isinstance(data.get("embedding"), dict):
        values = data["embedding"].get("values") or []
    elif data.get("embeddings"):
        values = (data["embeddings"][0] or {}).get("values") or []

    if not values:
        print("[ERROR] No embedding vector returned.")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1200])
        return 1

    print("[OK] Embedding generated successfully.")
    print(f"vector dim: {len(values)}")
    print(f"vector[:8]: {values[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
