from unittest.mock import Mock, patch

import httpx
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from google.genai.errors import APIError

from apps.gemini import safe_gemini_error
from apps.assessments.services.gemini import GoogleGeminiLLM
from apps.assessments.services.llm import get_llm_provider


class GoogleGeminiLLMTests(SimpleTestCase):
    @override_settings(
        GEMINI_API_KEY='test-key',
        GEMINI_TIMEOUT_SECONDS=7,
        LLM_PROVIDER='google',
        LLM_MODEL='gemini-3.8-flash',
    )
    @patch('apps.assessments.services.gemini.create_gemini_client')
    def test_provider_uses_google_sdk_and_json_output(self, create_client):
        client = Mock()
        client.models.generate_content.return_value.text = '{"ok":true}'
        create_client.return_value = client

        schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}}
        result = get_llm_provider().generate('system rules', 'user prompt', response_schema=schema)

        self.assertEqual(result, '{"ok":true}')
        request = client.models.generate_content.call_args.kwargs
        self.assertEqual(request['model'], 'gemini-3.8-flash')
        self.assertEqual(request['contents'], 'user prompt')
        self.assertEqual(request['config'].system_instruction, 'system rules')
        self.assertEqual(request['config'].response_mime_type, 'application/json')
        self.assertEqual(request['config'].response_json_schema, schema)
        client.close.assert_called_once_with()

    @override_settings(GEMINI_API_KEY='', LLM_MODEL='gemini-3.8-flash')
    def test_missing_api_key_fails_before_network_request(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'GEMINI_API_KEY'):
            GoogleGeminiLLM()

    @override_settings(GEMINI_API_KEY='test-key', LLM_MODEL='')
    def test_missing_model_fails_at_provider_initialization(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'LLM_MODEL'):
            GoogleGeminiLLM()

    @override_settings(GEMINI_API_KEY='test-key', LLM_MODEL='gemini-3.8-flash')
    @patch('apps.assessments.services.gemini.create_gemini_client')
    def test_invalid_key_error_is_safe_and_actionable(self, create_client):
        client = Mock()
        client.models.generate_content.side_effect = APIError(400, {
            'error': {'message': 'API key not valid. This private message must not be forwarded.'},
        })
        create_client.return_value = client

        with self.assertRaisesMessage(ImproperlyConfigured, 'GEMINI_API_KEY') as caught:
            GoogleGeminiLLM().generate('system', 'user')
        self.assertNotIn('private message', str(caught.exception))
        client.close.assert_called_once_with()

    @override_settings(GEMINI_API_KEY='test-key', LLM_MODEL='gemini-3.8-flash')
    @patch('apps.assessments.services.gemini.create_gemini_client')
    def test_timeout_and_rate_limit_errors_are_clear(self, create_client):
        client = Mock()
        client.models.generate_content.side_effect = httpx.ReadTimeout('opaque timeout details')
        create_client.return_value = client
        with self.assertRaisesRegex(TimeoutError, 'timed out'):
            GoogleGeminiLLM().generate('system', 'user')
        self.assertNotIn('opaque', str(safe_gemini_error(httpx.ReadTimeout('opaque'), 'test')))

        client = Mock()
        client.models.generate_content.side_effect = APIError(429, {'error': {'message': 'quota text'}})
        create_client.return_value = client
        with self.assertRaisesRegex(RuntimeError, 'rate limit'):
            GoogleGeminiLLM().generate('system', 'user')
        self.assertNotIn('quota text', str(safe_gemini_error(APIError(429, {'error': {'message': 'quota text'}}), 'test')))

    def test_overload_errors_are_actionable_without_forwarding_provider_details(self):
        error = APIError(503, {'error': {'message': 'The service is overloaded; private diagnostics must not leak.'}})

        safe_error = safe_gemini_error(error, 'question generation')

        self.assertIn('currently overloaded', str(safe_error))
        self.assertIn('retry later', str(safe_error))
        self.assertNotIn('private diagnostics', str(safe_error))

    @override_settings(GEMINI_API_KEY='test-key', LLM_MODEL='gemini-3.8-flash')
    @patch('apps.assessments.services.gemini.create_gemini_client')
    def test_empty_model_response_is_rejected(self, create_client):
        client = Mock()
        client.models.generate_content.return_value.text = None
        create_client.return_value = client
        with self.assertRaisesRegex(RuntimeError, 'empty JSON response'):
            GoogleGeminiLLM().generate('system', 'user')
