"""Google Gemini implementation for the existing assessment LLM interface."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from google.genai import types

from apps.gemini import close_gemini_client, create_gemini_client, safe_gemini_error


class GoogleGeminiLLM:
    def __init__(self):
        if not settings.LLM_MODEL:
            raise ImproperlyConfigured('Set LLM_MODEL before requesting Gemini assessment processing.')
        self.client = create_gemini_client()

    def generate(self, system_prompt, user_prompt, *, response_schema=None):
        try:
            response = self.client.models.generate_content(
                model=settings.LLM_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type='application/json',
                    response_json_schema=response_schema,
                ),
            )
            content = response.text
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError('Gemini returned an empty JSON response.')
            return content
        except Exception as exc:
            if isinstance(exc, (ImproperlyConfigured, RuntimeError)):
                raise
            raise safe_gemini_error(exc, 'LLM generation') from exc
        finally:
            close_gemini_client(self.client)
