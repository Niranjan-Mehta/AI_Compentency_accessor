"""Configurable OpenAI-compatible chat-completions client for question generation."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .gemini import GoogleGeminiLLM


class OpenAICompatibleLLM:
    def generate(self, system_prompt, user_prompt, *, response_schema=None):
        if settings.LLM_PROVIDER != 'http':
            raise ImproperlyConfigured(f'Unknown LLM provider: {settings.LLM_PROVIDER}')
        if not settings.LLM_API_URL or not settings.LLM_MODEL:
            raise ImproperlyConfigured('Set LLM_API_URL and LLM_MODEL before requesting AI assessment processing.')

        payload = json.dumps({
            'model': settings.LLM_MODEL,
            'temperature': 0.2,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        }).encode('utf-8')
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if settings.LLM_API_KEY:
            headers['Authorization'] = f'Bearer {settings.LLM_API_KEY}'
        request = Request(settings.LLM_API_URL, data=payload, headers=headers, method='POST')
        try:
            with urlopen(request, timeout=settings.LLM_TIMEOUT_SECONDS) as response:
                result = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError('Question generation provider request failed.') from exc

        try:
            content = result['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError('Question generation provider returned an unexpected response.') from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError('Question generation provider returned empty content.')
        return content


def get_llm_provider():
    if settings.LLM_PROVIDER == 'google':
        return GoogleGeminiLLM()
    return OpenAICompatibleLLM()
