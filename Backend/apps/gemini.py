"""Shared, secret-safe Gemini SDK setup and error translation."""

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from google import genai
from google.genai import errors, types


def create_gemini_client():
    if not settings.GEMINI_API_KEY:
        raise ImproperlyConfigured('Set GEMINI_API_KEY to use the Google Gemini providers.')
    if settings.GEMINI_TIMEOUT_SECONDS <= 0:
        raise ImproperlyConfigured('GEMINI_TIMEOUT_SECONDS must be a positive number.')
    try:
        return genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000,
                retry_options=types.HttpRetryOptions(
                    attempts=3,
                    initial_delay=1,
                    max_delay=8,
                    jitter=1,
                ),
            ),
        )
    except Exception as exc:
        raise ImproperlyConfigured('Gemini client initialization failed; verify the SDK configuration.') from exc


def safe_gemini_error(exc, operation):
    """Return a safe public error without forwarding provider response bodies."""
    if isinstance(exc, errors.APIError):
        code = exc.code
        message = (getattr(exc, 'message', '') or '').lower()
        if code in (401, 403) or 'api key not valid' in message or 'api_key_invalid' in message:
            return ImproperlyConfigured('Gemini rejected GEMINI_API_KEY; verify the key configuration.')
        if code == 429:
            return RuntimeError(f'Gemini rate limit reached during {operation}; retry later.')
        if code == 404:
            return ImproperlyConfigured(f'Gemini model configuration was rejected during {operation}.')
        if code is not None and code >= 500:
            if any(term in message for term in ('overload', 'high demand', 'capacity')):
                return RuntimeError(f'Gemini is currently overloaded during {operation}; retry later.')
            return RuntimeError(f'Gemini service is temporarily unavailable during {operation}; retry later.')
        return RuntimeError(f'Gemini {operation} request failed (HTTP {code}).')
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return TimeoutError(f'Gemini {operation} request timed out.')
    if isinstance(exc, (httpx.TransportError, OSError)):
        return RuntimeError(f'Gemini {operation} service could not be reached.')
    return RuntimeError(f'Gemini {operation} request failed.')


def close_gemini_client(client):
    try:
        client.close()
    except Exception:
        pass
