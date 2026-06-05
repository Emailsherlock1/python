"""HTTP client for the EmailSherlock verify API. Zero third-party dependencies."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from ._version import __version__
from .errors import EmailsherlockError, error_from_response
from .models import BatchResponse, VerifyResult

DEFAULT_BASE_URL = "https://api.emailsherlock.com"


def _num(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class _VerifyResource:
    """Verify-endpoint methods, reached as ``client.verify``."""

    def __init__(self, client: "Emailsherlock") -> None:
        self._client = client

    def single(self, email: str) -> VerifyResult:
        """Verify a single address."""
        data = self._client._request("/v1/verify/single", {"email": email})
        return VerifyResult.from_dict(data)

    def batch(self, emails: List[str]) -> BatchResponse:
        """Verify up to 100 addresses in one call."""
        data = self._client._request("/v1/verify/batch", {"emails": list(emails)})
        return BatchResponse.from_dict(data)


class Emailsherlock:
    """Client for the EmailSherlock verify API.

    The API key is read from ``api_key`` or, if omitted, from the ``ES_KEY`` /
    ``EMAILSHERLOCK_API_KEY`` environment variables.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        key = api_key or os.environ.get("ES_KEY") or os.environ.get("EMAILSHERLOCK_API_KEY")
        if not key:
            raise EmailsherlockError(
                "No API key provided. Pass api_key= or set ES_KEY.",
                code="config_error",
            )
        self._api_key = key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        #: credits left after the most recent request (X-Credits-Remaining)
        self.credits_remaining: Optional[float] = None
        #: rate-limit window after the most recent request (X-RateLimit-*)
        self.rate_limit: Dict[str, Optional[float]] = {
            "limit": None,
            "remaining": None,
            "reset": None,
        }

        self.verify = _VerifyResource(self)

    def _request(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._base_url + path
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "X-API-Key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "emailsherlock-python/{}".format(__version__),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
                self._capture_meta(response.headers)
                status = response.status
                headers = response.headers
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            self._capture_meta(exc.headers)
            parsed = self._parse(raw)
            raise error_from_response(exc.code, parsed, exc.headers)
        except urllib.error.URLError as exc:
            raise EmailsherlockError(
                "Request to {} failed: {}".format(path, exc.reason),
                code="network_error",
            )

        parsed = self._parse(raw)
        if status >= 400:
            raise error_from_response(status, parsed, headers)
        return parsed if isinstance(parsed, dict) else {}

    def _capture_meta(self, headers: Any) -> None:
        credits = headers.get("X-Credits-Remaining")
        if credits is not None:
            self.credits_remaining = _num(credits)
        if headers.get("X-RateLimit-Limit") is not None:
            self.rate_limit = {
                "limit": _num(headers.get("X-RateLimit-Limit")),
                "remaining": _num(headers.get("X-RateLimit-Remaining")),
                "reset": _num(headers.get("X-RateLimit-Reset")),
            }

    @staticmethod
    def _parse(raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
