import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from google.genai.errors import APIError

from apps.submissions.embedding_providers import GoogleGeminiEmbeddingProvider, get_embedding_provider
from apps.submissions.vector_store import close_chroma_client, get_collection


def embedding_response(count, dimensions):
    return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.125] * dimensions) for _ in range(count)])


class GoogleGeminiEmbeddingTests(SimpleTestCase):
    @override_settings(
        GEMINI_API_KEY='test-key', EMBEDDING_MODEL='gemini-embedding-001',
        EMBEDDING_DIMENSIONS=128,
    )
    @patch('apps.submissions.embedding_providers.create_gemini_client')
    def test_documents_are_batched_at_provider_limit(self, create_client):
        client = Mock()
        client.models.embed_content.side_effect = [embedding_response(32, 128), embedding_response(1, 128)]
        create_client.return_value = client

        vectors = GoogleGeminiEmbeddingProvider().embed_documents([f'doc {i}' for i in range(33)])

        self.assertEqual(len(vectors), 33)
        self.assertEqual(client.models.embed_content.call_count, 2)
        self.assertEqual(len(client.models.embed_content.call_args_list[0].kwargs['contents']), 32)
        self.assertEqual(len(client.models.embed_content.call_args_list[1].kwargs['contents']), 1)

    @override_settings(
        GEMINI_API_KEY='test-key', GEMINI_TIMEOUT_SECONDS=10,
        EMBEDDING_PROVIDER='google', EMBEDDING_MODEL='gemini-embedding-001',
        EMBEDDING_DIMENSIONS=768,
    )
    @patch('apps.submissions.embedding_providers.create_gemini_client')
    def test_documents_use_retrieval_document_task_and_validate_dimensions(self, create_client):
        client = Mock()
        client.models.embed_content.return_value = embedding_response(2, 768)
        create_client.return_value = client

        vectors = get_embedding_provider().embed_documents(['source one', 'source two'])

        self.assertEqual([len(vector) for vector in vectors], [768, 768])
        request = client.models.embed_content.call_args.kwargs
        self.assertEqual(request['model'], 'gemini-embedding-001')
        self.assertEqual(request['contents'], ['source one', 'source two'])
        self.assertEqual(request['config'].task_type, 'RETRIEVAL_DOCUMENT')
        self.assertEqual(request['config'].output_dimensionality, 768)
        client.close.assert_called_once_with()

    @override_settings(
        GEMINI_API_KEY='test-key', EMBEDDING_MODEL='gemini-embedding-001',
        EMBEDDING_DIMENSIONS=768,
    )
    @patch('apps.submissions.embedding_providers.create_gemini_client')
    def test_query_task_type_matches_code_or_pdf_retrieval(self, create_client):
        first, second = Mock(), Mock()
        first.models.embed_content.return_value = embedding_response(1, 768)
        second.models.embed_content.return_value = embedding_response(1, 768)
        create_client.side_effect = [first, second]
        provider = GoogleGeminiEmbeddingProvider()

        provider.embed_query('find implementation', source_type='CODE')
        provider.embed_query('find explanation', source_type='PDF')

        self.assertEqual(first.models.embed_content.call_args.kwargs['config'].task_type, 'CODE_RETRIEVAL_QUERY')
        self.assertEqual(second.models.embed_content.call_args.kwargs['config'].task_type, 'RETRIEVAL_QUERY')
        first.close.assert_called_once_with()
        second.close.assert_called_once_with()

    @override_settings(
        GEMINI_API_KEY='test-key', EMBEDDING_MODEL='gemini-embedding-001',
        EMBEDDING_DIMENSIONS=768,
    )
    @patch('apps.submissions.embedding_providers.create_gemini_client')
    def test_embedding_count_dimension_and_api_errors_are_validated(self, create_client):
        client = Mock()
        client.models.embed_content.return_value = embedding_response(1, 3)
        create_client.return_value = client
        with self.assertRaisesRegex(RuntimeError, 'unexpected dimension'):
            GoogleGeminiEmbeddingProvider().embed_documents(['a'])

        client = Mock()
        client.models.embed_content.side_effect = APIError(429, {'error': {'message': 'quota details'}})
        create_client.return_value = client
        with self.assertRaisesRegex(RuntimeError, 'rate limit'):
            GoogleGeminiEmbeddingProvider().embed_documents(['a'])

    @override_settings(
        GEMINI_API_KEY='', EMBEDDING_PROVIDER='google',
        EMBEDDING_MODEL='gemini-embedding-001', EMBEDDING_DIMENSIONS=3072,
    )
    def test_missing_key_and_invalid_dimensions_fail_during_provider_initialization(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'GEMINI_API_KEY'):
            GoogleGeminiEmbeddingProvider()

        with override_settings(GEMINI_API_KEY='test-key', EMBEDDING_DIMENSIONS=64):
            with self.assertRaisesMessage(ImproperlyConfigured, 'between 128 and 3072'):
                GoogleGeminiEmbeddingProvider()


class GeminiChromaCollectionTests(SimpleTestCase):
    def test_gemini_uses_a_profiled_collection_and_rejects_profile_reuse(self):
        backend_dir = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix='.gemini-chroma-isolated-', dir=backend_dir) as directory:
            settings = {
                'CHROMA_PERSIST_DIRECTORY': Path(directory),
                'CHROMA_COLLECTION_NAME': 'gemini_embedding_test_768',
                'EMBEDDING_PROVIDER': 'google',
                'EMBEDDING_MODEL': 'gemini-embedding-001',
                'EMBEDDING_DIMENSIONS': 768,
            }
            try:
                with override_settings(**settings):
                    collection = get_collection()
                    self.assertEqual(collection.count(), 0)
                    self.assertEqual(collection.metadata['embedding_provider'], 'google')
                    self.assertEqual(collection.metadata['embedding_model'], 'gemini-embedding-001')
                    self.assertEqual(collection.metadata['embedding_dimensions'], 768)

                with override_settings(**{**settings, 'EMBEDDING_MODEL': 'different-model'}):
                    with self.assertRaisesMessage(ImproperlyConfigured, 'does not match'):
                        get_collection()
            finally:
                close_chroma_client(directory)
