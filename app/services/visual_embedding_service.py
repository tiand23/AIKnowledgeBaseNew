"""
视觉向量服务

设计目标：
- 文本向量继续沿用现有 OpenAI 链路
- 页面级图片向量单独走 Gemini 视觉 embedding
- 优先支持 AI Studio API key 路线，失败时按配置回退到 Vertex
- 未配置时返回 pending_config，保证主链路不受影响
"""
from __future__ import annotations

import base64
import mimetypes
import os
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.clients.minio_client import minio_client
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_VERTEX_SCOPE = ["https://www.googleapis.com/auth/cloud-platform"]
_BACKEND_AUTO = "auto"
_BACKEND_AI_STUDIO = "ai_studio"
_BACKEND_VERTEX = "vertex"


@dataclass
class VisualEmbeddingResult:
    vector: Optional[List[float]]
    status: str
    error_message: Optional[str] = None
    provider: str = "gemini"
    model_name: Optional[str] = None
    backend: Optional[str] = None
    embedding_dim: Optional[int] = None


class VisualEmbeddingService:

    def __init__(self) -> None:
        self.enabled = bool(settings.GEMINI_VISUAL_EMBEDDING_ENABLED)
        self.provider = "gemini"
        self.backend = str(settings.GEMINI_VISUAL_EMBEDDING_BACKEND or _BACKEND_AUTO).strip().lower() or _BACKEND_AUTO
        self.model_name = settings.GEMINI_VISUAL_EMBEDDING_MODEL
        self.dimensions = max(0, int(settings.GEMINI_VISUAL_EMBEDDING_DIMENSIONS))
        self.project_id = settings.GEMINI_VISUAL_EMBEDDING_PROJECT_ID.strip()
        self.location = settings.GEMINI_VISUAL_EMBEDDING_LOCATION.strip() or "us-central1"
        self.timeout_sec = max(10, int(settings.GEMINI_VISUAL_EMBEDDING_TIMEOUT_SEC))
        self.contextual_text_enabled = bool(settings.GEMINI_VISUAL_EMBEDDING_CONTEXTUAL_TEXT_ENABLED)
        self.api_key = (
            str(settings.GEMINI_API_KEY or "").strip()
            or str(os.getenv("GOOGLE_API_KEY") or "").strip()
            or str(os.getenv("GEMINI_API_KEY") or "").strip()
        )

    def is_ready(self) -> bool:
        if not self.enabled:
            return False
        if self.backend == _BACKEND_AI_STUDIO:
            return bool(self.api_key)
        if self.backend == _BACKEND_VERTEX:
            return bool(self.location)
        return bool(self.api_key) or bool(self.location)

    async def embed_image(
        self,
        image_path: str,
        contextual_text: Optional[str] = None,
    ) -> VisualEmbeddingResult:
        normalized_path = str(image_path or "").strip()
        if not normalized_path:
            return VisualEmbeddingResult(
                vector=None,
                status="skipped",
                error_message="image_path is empty",
                model_name=self.model_name,
                backend=self.backend,
            )

        if not self.enabled:
            return VisualEmbeddingResult(
                vector=None,
                status="pending_config",
                error_message="gemini visual embedding is disabled",
                model_name=self.model_name,
                backend=self.backend,
            )

        image_bytes = minio_client.download_file(settings.MINIO_DEFAULT_BUCKET, normalized_path)
        if not image_bytes:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message=f"failed to download image from MinIO: {normalized_path}",
                model_name=self.model_name,
                backend=self.backend,
            )

        backends = self._resolve_backend_order()
        if not backends:
            return VisualEmbeddingResult(
                vector=None,
                status="pending_config",
                error_message="no Gemini visual embedding backend is configured",
                model_name=self.model_name,
                backend=self.backend,
            )

        pending_errors: List[str] = []
        hard_errors: List[str] = []

        for backend in backends:
            try:
                if backend == _BACKEND_AI_STUDIO:
                    result = await self._embed_via_ai_studio(
                        image_bytes=image_bytes,
                        image_path=normalized_path,
                    )
                elif backend == _BACKEND_VERTEX:
                    result = await self._embed_via_vertex(
                        image_bytes=image_bytes,
                        image_path=normalized_path,
                        contextual_text=contextual_text,
                    )
                else:
                    pending_errors.append(f"unsupported backend: {backend}")
                    continue
            except Exception as e:
                logger.error(
                    "Gemini 视觉向量生成失败: backend=%s, model=%s, image_path=%s, error=%s",
                    backend,
                    self.model_name,
                    normalized_path,
                    e,
                    exc_info=True,
                )
                hard_errors.append(f"{backend}: {e}")
                continue

            if result.vector:
                return result

            if result.status in {"pending_config", "pending_provider", "skipped"}:
                pending_errors.append(f"{backend}: {result.error_message}")
                continue

            hard_errors.append(f"{backend}: {result.error_message}")

        if hard_errors:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message="; ".join(hard_errors[:3]),
                model_name=self.model_name,
                backend=",".join(backends),
            )

        return VisualEmbeddingResult(
            vector=None,
            status="pending_config",
            error_message="; ".join([err for err in pending_errors[:3] if err]) or "no usable Gemini visual embedding backend is ready",
            model_name=self.model_name,
            backend=",".join(backends),
        )

    async def embed_query_text(self, query_text: str) -> VisualEmbeddingResult:
        cleaned_query = str(query_text or "").strip()
        if not cleaned_query:
            return VisualEmbeddingResult(
                vector=None,
                status="skipped",
                error_message="query_text is empty",
                model_name=self.model_name,
                backend=self.backend,
            )

        if not self.enabled:
            return VisualEmbeddingResult(
                vector=None,
                status="pending_config",
                error_message="gemini visual embedding is disabled",
                model_name=self.model_name,
                backend=self.backend,
            )

        backends = self._resolve_backend_order()
        if not backends:
            return VisualEmbeddingResult(
                vector=None,
                status="pending_config",
                error_message="no Gemini visual embedding backend is configured",
                model_name=self.model_name,
                backend=self.backend,
            )

        pending_errors: List[str] = []
        hard_errors: List[str] = []

        for backend in backends:
            try:
                if backend == _BACKEND_AI_STUDIO:
                    result = await self._embed_query_via_ai_studio(cleaned_query)
                elif backend == _BACKEND_VERTEX:
                    result = await self._embed_query_via_vertex(cleaned_query)
                else:
                    pending_errors.append(f"unsupported backend: {backend}")
                    continue
            except Exception as e:
                logger.error(
                    "Gemini 视觉查询向量生成失败: backend=%s, model=%s, query='%s', error=%s",
                    backend,
                    self.model_name,
                    cleaned_query[:120],
                    e,
                    exc_info=True,
                )
                hard_errors.append(f"{backend}: {e}")
                continue

            if result.vector:
                return result

            if result.status in {"pending_config", "pending_provider", "skipped"}:
                pending_errors.append(f"{backend}: {result.error_message}")
                continue

            hard_errors.append(f"{backend}: {result.error_message}")

        if hard_errors:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message="; ".join(hard_errors[:3]),
                model_name=self.model_name,
                backend=",".join(backends),
            )

        return VisualEmbeddingResult(
            vector=None,
            status="pending_config",
            error_message="; ".join([err for err in pending_errors[:3] if err]) or "no usable Gemini query embedding backend is ready",
            model_name=self.model_name,
            backend=",".join(backends),
        )

    def _resolve_backend_order(self) -> List[str]:
        if self.backend in {_BACKEND_AI_STUDIO, _BACKEND_VERTEX}:
            return [self.backend]

        ordered: List[str] = []
        if self.api_key:
            ordered.append(_BACKEND_AI_STUDIO)
        ordered.append(_BACKEND_VERTEX)
        return ordered

    def _guess_mime_type(self, image_path: str) -> str:
        guessed, _ = mimetypes.guess_type(image_path)
        if guessed and guessed.startswith("image/"):
            return guessed
        return "image/png"

    async def _embed_via_ai_studio(
        self,
        *,
        image_bytes: bytes,
        image_path: str,
    ) -> VisualEmbeddingResult:
        if not self.api_key:
            return VisualEmbeddingResult(
                vector=None,
                status="pending_config",
                error_message="GEMINI_API_KEY / GOOGLE_API_KEY is not configured",
                model_name=self.model_name,
                backend=_BACKEND_AI_STUDIO,
            )

        try:
            vector = await self._request_ai_studio_embedding(
                image_bytes=image_bytes,
                image_path=image_path,
            )
        except Exception as e:
            logger.warning(
                "AI Studio 视觉向量调用失败: model=%s, image_path=%s, error=%s",
                self.model_name,
                image_path,
                e,
            )
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message=str(e),
                model_name=self.model_name,
                backend=_BACKEND_AI_STUDIO,
            )

        if not vector:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message="AI Studio returned an empty embedding vector",
                model_name=self.model_name,
                backend=_BACKEND_AI_STUDIO,
            )

        actual_dim = len(vector)
        if self.dimensions > 0 and actual_dim != self.dimensions:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message=f"AI Studio embedding dimension mismatch: expected={self.dimensions}, actual={actual_dim}",
                model_name=self.model_name,
                backend=_BACKEND_AI_STUDIO,
                embedding_dim=actual_dim,
            )

        return VisualEmbeddingResult(
            vector=vector,
            status="indexed",
            error_message=None,
            model_name=self.model_name,
            backend=_BACKEND_AI_STUDIO,
            embedding_dim=actual_dim,
        )

    async def _embed_via_vertex(
        self,
        *,
        image_bytes: bytes,
        image_path: str,
        contextual_text: Optional[str] = None,
    ) -> VisualEmbeddingResult:
        try:
            access_token = self._get_access_token()
        except Exception as e:
            logger.warning("获取 Vertex 访问令牌失败: %s", e)
            return VisualEmbeddingResult(
                vector=None,
                status="pending_config",
                error_message=f"Vertex ADC is not ready: {e}",
                model_name=self.model_name,
                backend=_BACKEND_VERTEX,
            )

        vector = await self._request_vertex_embedding(
            image_bytes=image_bytes,
            image_path=image_path,
            access_token=access_token,
            contextual_text=contextual_text,
        )
        if not vector:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message="empty embedding vector returned by Vertex",
                model_name=self.model_name,
                backend=_BACKEND_VERTEX,
            )

        actual_dim = len(vector)
        if self.dimensions > 0 and actual_dim != self.dimensions:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message=f"Vertex embedding dimension mismatch: expected={self.dimensions}, actual={actual_dim}",
                model_name=self.model_name,
                backend=_BACKEND_VERTEX,
                embedding_dim=actual_dim,
            )

        return VisualEmbeddingResult(
            vector=vector,
            status="indexed",
            error_message=None,
            model_name=self.model_name,
            backend=_BACKEND_VERTEX,
            embedding_dim=actual_dim,
        )

    async def _embed_query_via_ai_studio(self, query_text: str) -> VisualEmbeddingResult:
        if not self.api_key:
            return VisualEmbeddingResult(
                vector=None,
                status="pending_config",
                error_message="GEMINI_API_KEY / GOOGLE_API_KEY is not configured",
                model_name=self.model_name,
                backend=_BACKEND_AI_STUDIO,
            )

        try:
            vector = await self._request_ai_studio_text_embedding(query_text=query_text)
        except Exception as e:
            logger.warning(
                "AI Studio 查询向量调用失败: model=%s, query='%s', error=%s",
                self.model_name,
                query_text[:120],
                e,
            )
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message=str(e),
                model_name=self.model_name,
                backend=_BACKEND_AI_STUDIO,
            )

        if not vector:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message="AI Studio returned an empty query embedding vector",
                model_name=self.model_name,
                backend=_BACKEND_AI_STUDIO,
            )

        actual_dim = len(vector)
        if self.dimensions > 0 and actual_dim != self.dimensions:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message=f"AI Studio query embedding dimension mismatch: expected={self.dimensions}, actual={actual_dim}",
                model_name=self.model_name,
                backend=_BACKEND_AI_STUDIO,
                embedding_dim=actual_dim,
            )

        return VisualEmbeddingResult(
            vector=vector,
            status="indexed",
            error_message=None,
            model_name=self.model_name,
            backend=_BACKEND_AI_STUDIO,
            embedding_dim=actual_dim,
        )

    async def _embed_query_via_vertex(self, query_text: str) -> VisualEmbeddingResult:
        try:
            access_token = self._get_access_token()
        except Exception as e:
            logger.warning("获取 Vertex 查询访问令牌失败: %s", e)
            return VisualEmbeddingResult(
                vector=None,
                status="pending_config",
                error_message=f"Vertex ADC is not ready: {e}",
                model_name=self.model_name,
                backend=_BACKEND_VERTEX,
            )

        vector = await self._request_vertex_text_embedding(
            query_text=query_text,
            access_token=access_token,
        )
        if not vector:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message="empty query embedding vector returned by Vertex",
                model_name=self.model_name,
                backend=_BACKEND_VERTEX,
            )

        actual_dim = len(vector)
        if self.dimensions > 0 and actual_dim != self.dimensions:
            return VisualEmbeddingResult(
                vector=None,
                status="failed",
                error_message=f"Vertex query embedding dimension mismatch: expected={self.dimensions}, actual={actual_dim}",
                model_name=self.model_name,
                backend=_BACKEND_VERTEX,
                embedding_dim=actual_dim,
            )

        return VisualEmbeddingResult(
            vector=vector,
            status="indexed",
            error_message=None,
            model_name=self.model_name,
            backend=_BACKEND_VERTEX,
            embedding_dim=actual_dim,
        )

    def _build_vertex_endpoint(self) -> str:
        return (
            "https://"
            f"{self.location}-aiplatform.googleapis.com/v1/projects/"
            f"{self.project_id}/locations/{self.location}/publishers/google/models/"
            f"{self.model_name}:predict"
        )

    def _get_access_token(self) -> str:
        try:
            import google.auth
            from google.auth.transport.requests import Request
        except Exception as e:
            raise RuntimeError(
                "google-auth dependency is missing; install google-auth and requests"
            ) from e

        credentials, detected_project = google.auth.default(scopes=_VERTEX_SCOPE)
        if not credentials:
            raise RuntimeError("no Google application default credentials available")

        if not credentials.valid:
            credentials.refresh(Request())

        token = getattr(credentials, "token", None)
        if not token:
            raise RuntimeError("failed to obtain Vertex access token from ADC")

        if not self.project_id and detected_project:
            self.project_id = str(detected_project).strip()
        if not self.project_id:
            raise RuntimeError(
                "GEMINI_VISUAL_EMBEDDING_PROJECT_ID is not configured and ADC did not return a project id"
            )

        return token

    def _build_ai_studio_endpoint(self) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:embedContent"

    async def _request_ai_studio_embedding(
        self,
        *,
        image_bytes: bytes,
        image_path: str,
    ) -> List[float]:
        part = {
            "inline_data": {
                "mime_type": self._guess_mime_type(image_path),
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        }
        payload = {
            "model": f"models/{self.model_name}",
            "content": {
                "parts": [part],
            },
        }
        if self.dimensions > 0:
            payload["outputDimensionality"] = self.dimensions

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            response = await client.post(
                self._build_ai_studio_endpoint(),
                params={"key": self.api_key},
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"AI Studio embedContent failed: status={response.status_code}, body={response.text[:500]}"
            )

        data = response.json()
        if isinstance(data.get("embedding"), dict):
            values = data["embedding"].get("values") or []
            return [float(v) for v in values]

        embeddings = data.get("embeddings") or []
        if not embeddings:
            raise RuntimeError("AI Studio returned no embeddings")
        first = embeddings[0] or {}
        values = first.get("values") or []
        return [float(v) for v in values]

    async def _request_ai_studio_text_embedding(self, *, query_text: str) -> List[float]:
        payload = {
            "model": f"models/{self.model_name}",
            "content": {
                "parts": [{"text": query_text[:2048]}],
            },
        }
        if self.dimensions > 0:
            payload["outputDimensionality"] = self.dimensions

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            response = await client.post(
                self._build_ai_studio_endpoint(),
                params={"key": self.api_key},
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"AI Studio query embedContent failed: status={response.status_code}, body={response.text[:500]}"
            )

        data = response.json()
        if isinstance(data.get("embedding"), dict):
            values = data["embedding"].get("values") or []
            return [float(v) for v in values]

        embeddings = data.get("embeddings") or []
        if not embeddings:
            raise RuntimeError("AI Studio returned no query embeddings")
        first = embeddings[0] or {}
        values = first.get("values") or []
        return [float(v) for v in values]

    async def _request_vertex_embedding(
        self,
        *,
        image_bytes: bytes,
        image_path: str,
        access_token: str,
        contextual_text: Optional[str] = None,
    ) -> List[float]:
        instance = {
            "image": {
                "bytesBase64Encoded": base64.b64encode(image_bytes).decode("utf-8"),
                "mimeType": self._guess_mime_type(image_path),
            }
        }
        cleaned_context = str(contextual_text or "").strip()
        if self.contextual_text_enabled and cleaned_context:
            instance["text"] = cleaned_context[:128]

        payload = {
            "instances": [instance],
            "parameters": {
                "dimension": self.dimensions,
            },
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            response = await client.post(
                self._build_vertex_endpoint(),
                headers=headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Vertex predict failed: status={response.status_code}, body={response.text[:500]}"
            )

        data = response.json()
        predictions = data.get("predictions") or []
        if not predictions:
            raise RuntimeError("Vertex returned no predictions")

        first = predictions[0] or {}
        image_embedding = first.get("imageEmbedding") or []
        if not image_embedding:
            raise RuntimeError("Vertex returned no imageEmbedding")

        return [float(v) for v in image_embedding]

    async def _request_vertex_text_embedding(
        self,
        *,
        query_text: str,
        access_token: str,
    ) -> List[float]:
        payload = {
            "instances": [{"text": query_text[:2048]}],
            "parameters": {
                "dimension": self.dimensions,
            },
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            response = await client.post(
                self._build_vertex_endpoint(),
                headers=headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Vertex text predict failed: status={response.status_code}, body={response.text[:500]}"
            )

        data = response.json()
        predictions = data.get("predictions") or []
        if not predictions:
            raise RuntimeError("Vertex returned no text predictions")

        first = predictions[0] or {}
        text_embedding = (
            first.get("textEmbedding")
            or first.get("text_embedding")
            or first.get("embedding")
            or []
        )
        if not text_embedding:
            raise RuntimeError("Vertex returned no text embedding")

        return [float(v) for v in text_embedding]


visual_embedding_service = VisualEmbeddingService()
