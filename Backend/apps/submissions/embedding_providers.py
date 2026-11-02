"""Embedding API contract and configurable HTTP implementation."""

import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from google.genai import types

from apps.gemini import close_gemini_client, create_gemini_client, safe_gemini_error


class HTTPEmbeddingProvider:
    """Calls a configured embeddings endpoint using model/input JSON fields."""

    def embed_documents(self, texts):
        if not settings.EMBEDDING_API_URL or not settings.EMBEDDING_MODEL:
            raise ImproperlyConfigured('Set EMBEDDING_API_URL and EMBEDDING_MODEL to enable indexing.')
        vectors = []
        for offset in range(0, len(texts), 32):
            batch = texts[offset:offset + 32]
            payload = json.dumps({'model': settings.EMBEDDING_MODEL, 'input': batch}).encode('utf-8')
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
            if settings.EMBEDDING_API_KEY:
                headers['Authorization'] = f'Bearer {settings.EMBEDDING_API_KEY}'
            request = Request(settings.EMBEDDING_API_URL, data=payload, headers=headers, method='POST')
            try:
                with urlopen(request, timeout=45) as response:
                    result = json.loads(response.read())
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise RuntimeError('Embedding provider request failed.') from exc
            rows = result.get('data') if isinstance(result, dict) else None
            if not isinstance(rows, list) or len(rows) != len(batch):
                raise RuntimeError('Embedding provider returned an unexpected response.')
            try:
                rows.sort(key=lambda item: item.get('index', 0))
                vectors.extend([[float(value) for value in row['embedding']] for row in rows])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError('Embedding provider returned invalid vectors.') from exc
        if settings.EMBEDDING_DIMENSIONS and any(
            len(vector) != settings.EMBEDDING_DIMENSIONS for vector in vectors
        ):
            raise RuntimeError('Embedding provider returned vectors with an unexpected dimension.')
        return vectors

    def embed_query(self, text, *, source_type=None):
        return self.embed_documents([text])


class GoogleGeminiEmbeddingProvider:
    """Official Gemini embeddings with matched document/query dimensions."""

    BATCH_SIZE = 32
    MODEL_DIMENSIONS = (128, 3072)

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ImproperlyConfigured('Set GEMINI_API_KEY to use Gemini embeddings.')
        if not settings.EMBEDDING_MODEL:
            raise ImproperlyConfigured('Set EMBEDDING_MODEL before requesting Gemini embeddings.')
        dimensions = settings.EMBEDDING_DIMENSIONS or 3072
        if not self.MODEL_DIMENSIONS[0] <= dimensions <= self.MODEL_DIMENSIONS[1]:
            raise ImproperlyConfigured('Gemini EMBEDDING_DIMENSIONS must be between 128 and 3072.')
        self.dimensions = dimensions

    def embed_documents(self, texts):
        return self._embed(texts, task_type='RETRIEVAL_DOCUMENT')

    def embed_query(self, text, *, source_type=None):
        if not isinstance(text, str) or not text.strip():
            raise ValueError('An embedding query must contain text.')
        task_type = 'CODE_RETRIEVAL_QUERY' if source_type == 'CODE' else 'RETRIEVAL_QUERY'
        vectors = self._embed([text.strip()], task_type=task_type)
        return vectors

    def _embed(self, texts, *, task_type):
        if not isinstance(texts, (list, tuple)) or any(not isinstance(text, str) or not text.strip() for text in texts):
            if texts:
                raise ValueError('Embedding documents must be non-empty text strings.')
            return []

        client = create_gemini_client()
        vectors = []
        try:
            for offset in range(0, len(texts), self.BATCH_SIZE):
                batch = list(texts[offset:offset + self.BATCH_SIZE])
                response = client.models.embed_content(
                    model=settings.EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.dimensions,
                    ),
                )
                embeddings = getattr(response, 'embeddings', None) or []
                if len(embeddings) != len(batch):
                    raise RuntimeError('Gemini returned an unexpected number of embeddings.')
                for embedding in embeddings:
                    values = getattr(embedding, 'values', None)
                    if not isinstance(values, (list, tuple)) or len(values) != self.dimensions:
                        raise RuntimeError('Gemini returned an embedding with an unexpected dimension.')
                    try:
                        vector = [float(value) for value in values]
                    except (TypeError, ValueError) as exc:
                        raise RuntimeError('Gemini returned an invalid embedding vector.') from exc
                    if any(not math.isfinite(value) for value in vector):
                        raise RuntimeError('Gemini returned a non-finite embedding value.')
                    vectors.append(vector)
            return vectors
        except Exception as exc:
            if isinstance(exc, (ImproperlyConfigured, RuntimeError, ValueError)):
                raise
            raise safe_gemini_error(exc, 'embedding generation') from exc
        finally:
            close_gemini_client(client)


def get_embedding_provider():
    provider = settings.EMBEDDING_PROVIDER
    if provider == 'http':
        return HTTPEmbeddingProvider()
    if provider == 'google':
        return GoogleGeminiEmbeddingProvider()
    raise ImproperlyConfigured(f'Unknown embedding provider: {provider}')
