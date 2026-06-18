"""Ergonomic client for the EmailSherlock verify API.

Thin sugar over the generated raw client in ``emailsherlock._generated``:
named error classes, ``credits_remaining`` / ``rate_limit`` accessors, env-var
key fallback, and ``client.verify`` / ``client.guard`` / ``client.credits()``.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from ._generated.api.account_api import AccountApi
from ._generated.api.guard_api import GuardApi
from ._generated.api.verify_api import VerifyApi
from ._generated.api_client import ApiClient
from ._generated.configuration import Configuration
from ._generated.exceptions import ApiException, OpenApiException
from ._generated.models.guard_events_request import GuardEventsRequest
from ._generated.models.verify_batch_request import VerifyBatchRequest
from ._generated.models.verify_job_request import VerifyJobRequest
from ._generated.models.verify_single_request import VerifySingleRequest
from ._version import __version__
from .errors import EmailsherlockError, error_from_api_exception
from .models import (
    AccountStatusResponse,
    BatchItem,
    BatchResponse,
    VerifyJobResponse,
    VerifyResultResponse,
)

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
        self._api = VerifyApi(client._api_client)

    def single(self, email: str) -> VerifyResultResponse:
        """Verify a single address."""
        return self._client._call(
            lambda t: self._api.verify_single_with_http_info(
                VerifySingleRequest(email=email), _request_timeout=t
            )
        )

    def batch(self, emails: List[str]) -> BatchResponse:
        """Verify a batch of addresses in one call."""
        resp = self._client._call(
            lambda t: self._api.verify_batch_with_http_info(
                VerifyBatchRequest(emails=list(emails)), _request_timeout=t
            )
        )
        # Unwrap the generated oneOf wrapper to a flat list, matching v0.1.0.
        items: List[BatchItem] = [entry.actual_instance for entry in resp.results]
        return BatchResponse(results=items)

    def submit_job(self, emails: List[str]) -> VerifyJobResponse:
        """Submit a list of addresses for asynchronous verification. Poll with ``get_job``."""
        return self._client._call(
            lambda t: self._api.submit_verify_job_with_http_info(
                VerifyJobRequest(emails=list(emails)), _request_timeout=t
            )
        )

    def get_job(self, job_id: str) -> VerifyJobResponse:
        """Read the status and results of a verification job."""
        return self._client._call(
            lambda t: self._api.get_verify_job_with_http_info(job_id, _request_timeout=t)
        )


class _GuardResource:
    """Email-Guard event methods, reached as ``client.guard``."""

    def __init__(self, client: "Emailsherlock") -> None:
        self._client = client
        self._api = GuardApi(client._api_client)

    def record_events(self, events: List[Dict[str, Any]]) -> None:
        """Record a batch of Email-Guard decision events (free, no credits)."""
        self._client._call(
            lambda t: self._api.record_guard_events_with_http_info(
                GuardEventsRequest(events=list(events)), _request_timeout=t
            )
        )
        return None


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

        self._timeout = timeout
        configuration = Configuration(
            host=base_url.rstrip("/"),
            api_key={"ApiKeyAuth": key},
        )
        self._api_client = ApiClient(configuration)
        self._api_client.user_agent = "emailsherlock-python/{}".format(__version__)
        self._account = AccountApi(self._api_client)

        #: credits left after the most recent request (X-Credits-Remaining)
        self.credits_remaining: Optional[float] = None
        #: rate-limit window after the most recent request (X-RateLimit-*)
        self.rate_limit: Dict[str, Optional[float]] = {
            "limit": None,
            "remaining": None,
            "reset": None,
        }

        self.verify = _VerifyResource(self)
        self.guard = _GuardResource(self)

    def credits(self) -> AccountStatusResponse:
        """Read the credit balance and rate-limit status. Free: consumes no credits."""
        return self._call(lambda t: self._account.get_credits_with_http_info(_request_timeout=t))

    def _call(self, fn: Callable[[float], Any]) -> Any:
        """Run a raw-client call, capture meta headers, map errors to our classes."""
        try:
            response = fn(self._timeout)
        except ApiException as exc:
            if getattr(exc, "headers", None):
                self._capture_meta(exc.headers)
            raise error_from_api_exception(exc) from exc
        except OpenApiException as exc:
            raise EmailsherlockError(str(exc) or "Request failed.", code="network_error") from exc
        except (OSError, ValueError) as exc:  # urllib3 transport / connection failures
            raise EmailsherlockError(
                "Request failed: {}".format(exc), code="network_error"
            ) from exc

        self._capture_meta(response.headers)
        return response.data

    def _capture_meta(self, headers: Any) -> None:
        if not headers:
            return
        getter = headers.get
        credits = getter("X-Credits-Remaining")
        if credits is not None:
            self.credits_remaining = _num(credits)
        if getter("X-RateLimit-Limit") is not None:
            self.rate_limit = {
                "limit": _num(getter("X-RateLimit-Limit")),
                "remaining": _num(getter("X-RateLimit-Remaining")),
                "reset": _num(getter("X-RateLimit-Reset")),
            }
