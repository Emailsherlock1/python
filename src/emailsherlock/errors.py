"""Exception hierarchy. Every failure raises a subclass of EmailsherlockError."""
from __future__ import annotations

from typing import Any, Dict, Optional


def _num(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class EmailsherlockError(Exception):
    """Base class for every error this client raises."""

    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


class AuthenticationError(EmailsherlockError):
    """401 - missing or invalid API key."""


class ForbiddenError(EmailsherlockError):
    """403 - the key lacks the scope this endpoint needs."""

    def __init__(self, *args: Any, required_scope: Optional[str] = None, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.required_scope = required_scope


class InsufficientCreditsError(EmailsherlockError):
    """402 - not enough credits on the wallet for this request."""

    def __init__(
        self,
        *args: Any,
        credits_required: Optional[float] = None,
        credits_remaining: Optional[float] = None,
        **kw: Any,
    ) -> None:
        super().__init__(*args, **kw)
        self.credits_required = credits_required
        self.credits_remaining = credits_remaining


class RateLimitError(EmailsherlockError):
    """429 - per-key sliding-window rate limit hit."""

    def __init__(
        self,
        *args: Any,
        retry_after: Optional[float] = None,
        limit: Optional[float] = None,
        remaining: Optional[float] = None,
        reset: Optional[float] = None,
        **kw: Any,
    ) -> None:
        super().__init__(*args, **kw)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset = reset


class ValidationError(EmailsherlockError):
    """400 / 404 / 422 - the request was rejected, or the job was not found."""


class ServiceUnavailableError(EmailsherlockError):
    """503 - the verify engine could not answer; the credit was auto-refunded."""


def error_from_response(
    status: int,
    body: Optional[Dict[str, Any]],
    headers: Any,
) -> EmailsherlockError:
    envelope = (body or {}).get("error", {}) if isinstance(body, dict) else {}
    code = envelope.get("code")
    message = envelope.get("message") or "HTTP {}".format(status)

    if status == 401:
        return AuthenticationError(message, status=status, code=code)
    if status == 403:
        return ForbiddenError(
            message,
            status=status,
            code=code,
            required_scope=envelope.get("required_scope") or headers.get("X-Required-Scope"),
        )
    if status == 402:
        return InsufficientCreditsError(
            message,
            status=status,
            code=code,
            credits_required=_num(headers.get("X-Credits-Required")),
            credits_remaining=_num(headers.get("X-Credits-Remaining")),
        )
    if status == 429:
        return RateLimitError(
            message,
            status=status,
            code=code,
            retry_after=_num(headers.get("Retry-After")),
            limit=_num(headers.get("X-RateLimit-Limit")),
            remaining=_num(headers.get("X-RateLimit-Remaining")),
            reset=_num(headers.get("X-RateLimit-Reset")),
        )
    if status in (400, 404, 422):
        return ValidationError(message, status=status, code=code)
    if status == 503:
        return ServiceUnavailableError(message, status=status, code=code)
    return EmailsherlockError(message, status=status, code=code)


def error_from_api_exception(exc: Any) -> EmailsherlockError:
    """Map the generated ``ApiException`` to one of our named errors.

    The raw client raises ``ApiException`` (status + JSON body string + headers)
    for non-2xx responses. Anything else (transport failure) is rewrapped so
    callers only ever catch ``EmailsherlockError``.
    """
    import json

    status = getattr(exc, "status", None)
    headers = getattr(exc, "headers", None) or {}
    body: Optional[Dict[str, Any]] = None
    raw = getattr(exc, "body", None) or getattr(exc, "data", None)
    if isinstance(raw, (str, bytes)):
        try:
            body = json.loads(raw)
        except (ValueError, TypeError):
            body = None
    elif isinstance(raw, dict):
        body = raw

    if isinstance(status, int):
        return error_from_response(status, body, headers)
    return EmailsherlockError(str(exc) or "Request failed.", code="network_error")
