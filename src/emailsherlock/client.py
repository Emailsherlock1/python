"""Ergonomic client for the EmailSherlock API.

Thin sugar over the generated raw client in ``emailsherlock._generated``:
named error classes, ``credits_remaining`` / ``rate_limit`` accessors, env-var
key fallback, and the resources ``client.verify``, ``client.guard``,
``client.deliverability``, ``client.dmarc``, ``client.tls_rpt``,
``client.domains`` and ``client.impersonation``, plus ``client.credits()``.
"""
from __future__ import annotations

import datetime
import os
from typing import Any, Callable, Dict, List, Optional, Union

from ._generated.api.account_api import AccountApi
from ._generated.api.deliverability_api import DeliverabilityApi
from ._generated.api.domain_reports_api import DomainReportsApi
from ._generated.api.domain_setup_api import DomainSetupApi
from ._generated.api.guard_api import GuardApi
from ._generated.api.impersonation_api import ImpersonationApi
from ._generated.api.verify_api import VerifyApi
from ._generated.api_client import ApiClient
from ._generated.configuration import Configuration
from ._generated.exceptions import ApiException, OpenApiException
from ._generated.models.guard_events_request import GuardEventsRequest
from ._generated.models.impersonation_analyze_request import ImpersonationAnalyzeRequest
from ._generated.models.set_check_webhook_request import SetCheckWebhookRequest
from ._generated.models.verify_batch_request import VerifyBatchRequest
from ._generated.models.verify_job_request import VerifyJobRequest
from ._generated.models.verify_single_request import VerifySingleRequest
from ._version import __version__
from .errors import EmailsherlockError, error_from_api_exception
from .models import (
    AccountStatusResponse,
    BatchItem,
    BatchResponse,
    DeliverabilityLatestVerdictResource,
    DeliverabilityWebhookResource,
    DmarcSetupResource,
    DmarcSummaryResource,
    GetCheck200Response,
    ImpersonationAnalyzeResponse,
    ListCheckAddresses200Response,
    ListChecks200Response,
    ListDmarcReports200Response,
    ListDmarcSources200Response,
    ListDomainChanges200Response,
    ListTlsRptReports200Response,
    NextStepsResource,
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


def _set(**params: Any) -> Dict[str, Any]:
    """The optional parameters the caller set, so unset ones stay off the wire."""
    return {k: v for k, v in params.items() if v is not None}


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


class _DeliverabilityResource:
    """Deliverability check-address methods, reached as ``client.deliverability``. Free."""

    def __init__(self, client: "Emailsherlock") -> None:
        self._client = client
        self._api = DeliverabilityApi(client._api_client)

    def list_addresses(self) -> ListCheckAddresses200Response:
        """List your check addresses, each with its latest verdict."""
        return self._client._call(
            lambda t: self._api.list_check_addresses_with_http_info(_request_timeout=t)
        )

    def latest(self, id: int) -> DeliverabilityLatestVerdictResource:
        """The pre-send gate: the latest cached verdict for an address, without a live probe."""
        return self._client._call(
            lambda t: self._api.get_latest_verdict_with_http_info(id, _request_timeout=t)
        )

    def list_checks(
        self,
        id: int,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListChecks200Response:
        """The check log for one address, newest first."""
        params = _set(limit=limit, offset=offset)
        return self._client._call(
            lambda t: self._api.list_checks_with_http_info(id, _request_timeout=t, **params)
        )

    def get_check(self, id: int) -> GetCheck200Response:
        """One check with its full audit breakdown."""
        return self._client._call(
            lambda t: self._api.get_check_with_http_info(id, _request_timeout=t)
        )

    def set_webhook(self, id: int, url: str) -> DeliverabilityWebhookResource:
        """Set or replace the ``check.completed`` webhook of an address.

        The response carries the signing secret in ``webhook.secret``; the API
        shows it on this call only.
        """
        return self._client._call(
            lambda t: self._api.set_check_webhook_with_http_info(
                id, SetCheckWebhookRequest(url=url), _request_timeout=t
            )
        )

    def delete_webhook(self, id: int) -> DeliverabilityWebhookResource:
        """Remove the ``check.completed`` webhook of an address."""
        return self._client._call(
            lambda t: self._api.delete_check_webhook_with_http_info(id, _request_timeout=t)
        )


class _DmarcResource:
    """DMARC setup and report methods, reached as ``client.dmarc``. Free.

    The report reads (``summary``, ``reports``, ``sources``) need your account's
    report address in the domain's DMARC record.
    """

    def __init__(self, client: "Emailsherlock") -> None:
        self._client = client
        self._setup = DomainSetupApi(client._api_client)
        self._reports = DomainReportsApi(client._api_client)

    def start(self, domain: str) -> DmarcSetupResource:
        """Watch a domain and get the DMARC record to publish so its reports reach you."""
        return self._client._call(
            lambda t: self._setup.start_dmarc_monitoring_with_http_info(domain, _request_timeout=t)
        )

    def check(self, domain: str) -> DmarcSetupResource:
        """Look up the domain's DMARC record now and say whether it carries your report address."""
        return self._client._call(
            lambda t: self._setup.check_dmarc_setup_with_http_info(domain, _request_timeout=t)
        )

    def summary(self, domain: str, *, range: Optional[int] = None) -> DmarcSummaryResource:
        """Totals of the domain's DMARC reports over ``range`` days (7 or 30)."""
        params = _set(range=range)
        return self._client._call(
            lambda t: self._reports.get_dmarc_summary_with_http_info(
                domain, _request_timeout=t, **params
            )
        )

    def reports(
        self,
        domain: str,
        *,
        from_: Optional[Union[datetime.date, str]] = None,
        to: Optional[Union[datetime.date, str]] = None,
        reporter: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListDmarcReports200Response:
        """The domain's DMARC aggregate reports, newest first.

        ``from_`` and ``to`` take a ``date`` or a ``YYYY-MM-DD`` string (UTC) and
        are sent as the ``from`` and ``to`` query parameters.
        """
        params = _set(var_from=from_, to=to, reporter=reporter, limit=limit, offset=offset)
        return self._client._call(
            lambda t: self._reports.list_dmarc_reports_with_http_info(
                domain, _request_timeout=t, **params
            )
        )

    def sources(
        self,
        domain: str,
        *,
        range: Optional[int] = None,
        result: Optional[str] = None,
        check: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListDmarcSources200Response:
        """The rows of the dashboard's senders table for the domain.

        ``result`` is ``pass`` or ``fail``; ``check`` is ``dmarc``, ``spf`` or ``dkim``.
        """
        params = _set(range=range, result=result, check=check, limit=limit, offset=offset)
        return self._client._call(
            lambda t: self._reports.list_dmarc_sources_with_http_info(
                domain, _request_timeout=t, **params
            )
        )


class _TlsRptResource:
    """TLS-RPT report methods, reached as ``client.tls_rpt``. Free.

    Needs your account's report address in the domain's TLS-RPT record.
    """

    def __init__(self, client: "Emailsherlock") -> None:
        self._client = client
        self._api = DomainReportsApi(client._api_client)

    def reports(
        self,
        domain: str,
        *,
        range: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListTlsRptReports200Response:
        """The TLS-RPT reports your account received for the domain, newest first."""
        params = _set(range=range, limit=limit, offset=offset)
        return self._client._call(
            lambda t: self._api.list_tls_rpt_reports_with_http_info(
                domain, _request_timeout=t, **params
            )
        )


class _DomainsResource:
    """Watched-domain methods, reached as ``client.domains``. Free."""

    def __init__(self, client: "Emailsherlock") -> None:
        self._client = client
        self._api = DomainReportsApi(client._api_client)

    def changes(
        self,
        domain: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListDomainChanges200Response:
        """The timeline of a domain you watch: DNS, record and mail changes, newest first."""
        params = _set(limit=limit, offset=offset)
        return self._client._call(
            lambda t: self._api.list_domain_changes_with_http_info(
                domain, _request_timeout=t, **params
            )
        )

    def next_steps(self, domain: str) -> NextStepsResource:
        """What to change next on the domain on its way to ``p=reject``.

        Needs your account's report address in the domain's DMARC record.
        """
        return self._client._call(
            lambda t: self._api.get_domain_next_steps_with_http_info(domain, _request_timeout=t)
        )


class _ImpersonationResource:
    """Impersonation scoring, reached as ``client.impersonation``. Costs credits."""

    def __init__(self, client: "Emailsherlock") -> None:
        self._client = client
        self._api = ImpersonationApi(client._api_client)

    def analyze(
        self,
        from_: str,
        protected: List[Dict[str, Any]],
        *,
        display_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        dmarc: Optional[str] = None,
    ) -> ImpersonationAnalyzeResponse:
        """Score whether one message's sender poses as one of your protected identities.

        ``from_`` is the bare From address (sent as ``from``). Each entry of
        ``protected`` is a dict with ``name`` and optional ``domains`` /
        ``addresses``. No subject or body is sent.
        """
        body: Dict[str, Any] = {"from": from_, "protected": list(protected)}
        body.update(_set(display_name=display_name, reply_to=reply_to, dmarc=dmarc))
        # model_validate, not from_dict: from_dict marks every field as set, so the
        # nullable ones the caller left out would go out as explicit nulls.
        return self._client._call(
            lambda t: self._api.analyze_impersonation_with_http_info(
                ImpersonationAnalyzeRequest.model_validate(body), _request_timeout=t
            )
        )


class Emailsherlock:
    """Client for the EmailSherlock API.

    The API key is read from ``api_key`` or, if omitted, from the ``ES_KEY`` /
    ``EMAILSHERLOCK_API_KEY`` environment variables.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        client_id: Optional[int] = None,
    ) -> None:
        key = api_key or os.environ.get("ES_KEY") or os.environ.get("EMAILSHERLOCK_API_KEY")
        if not key:
            raise EmailsherlockError(
                "No API key provided. Pass api_key= or set ES_KEY.",
                code="config_error",
            )

        if client_id is not None and (
            isinstance(client_id, bool) or not isinstance(client_id, int) or client_id <= 0
        ):
            raise EmailsherlockError(
                "client_id must be a positive integer.",
                code="config_error",
            )

        self._key = key
        self._base_url = base_url
        self._timeout = timeout
        self._client_id = client_id
        configuration = Configuration(
            host=base_url.rstrip("/"),
            api_key={"ApiKeyAuth": key},
        )
        self._api_client = ApiClient(configuration)
        self._api_client.user_agent = "emailsherlock-python/{}".format(__version__)
        if client_id is not None:
            self._api_client.set_default_header("X-Client-Id", str(client_id))
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
        self.deliverability = _DeliverabilityResource(self)
        self.dmarc = _DmarcResource(self)
        self.tls_rpt = _TlsRptResource(self)
        self.domains = _DomainsResource(self)
        self.impersonation = _ImpersonationResource(self)

    @property
    def client_id(self) -> Optional[int]:
        """The tenant id sent as ``X-Client-Id``, or ``None`` in the key's own account."""
        return self._client_id

    def with_client_id(self, client_id: int) -> "Emailsherlock":
        """Return a new client for one tenant, with the same key, base URL and timeout.

        This client is left unchanged. The two keep separate credit and rate-limit meta.
        """
        return Emailsherlock(
            self._key,
            base_url=self._base_url,
            timeout=self._timeout,
            client_id=client_id,
        )

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
