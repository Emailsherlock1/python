"""Unit tests with a stubbed REST layer. No network.

The client wraps the generated urllib3-based raw client, so we stub
``RESTClientObject.request`` (the single HTTP seam) rather than urllib.
"""
import datetime
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import emailsherlock
from emailsherlock import (
    AuthenticationError,
    Emailsherlock,
    InsufficientCreditsError,
    RateLimitError,
    is_verify_result,
)
from emailsherlock._generated import rest


class FakeHeaders(dict):
    """Case-insensitive header lookup, like urllib3's HTTPHeaderDict."""

    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


class FakeRESTResponse:
    def __init__(self, status, body, headers):
        self.status = status
        self.reason = "stub"
        self.data = b"" if body is None else json.dumps(body).encode()
        self.headers = FakeHeaders({"content-type": "application/json", **(headers or {})})

    def read(self):
        return self.data

    def getheaders(self):
        return self.headers


def stub(monkeypatch, status, body, headers=None):
    def _request(self, method, url, headers=None, body=None, post_params=None,
                 _request_timeout=None, **kw):
        return FakeRESTResponse(status, _request.body, _request.headers)
    _request.body = body
    _request.headers = headers
    monkeypatch.setattr(rest.RESTClientObject, "request", _request)


WIRE = {
    "email": "jane@acme.com", "result": "valid", "mx": True, "mx_record": "mx1.acme.com",
    "disposable": False, "role": False, "catch_all": True, "free_email": False,
    "relay": False, "parked": False, "spam_trap": False,
    "score": 0.95, "freshness": "fresh", "checked_at": "2026-06-09T14:32:00+00:00",
    "decision": {"recommendation": "allow", "reasons": ["mailbox_accepts"]},
}


def test_single_returns_result_and_captures_meta(monkeypatch):
    stub(monkeypatch, 200, WIRE, {
        "X-Credits-Remaining": "41", "X-RateLimit-Limit": "60",
        "X-RateLimit-Remaining": "59", "X-RateLimit-Reset": "1700000000",
    })
    es = Emailsherlock("test-key")
    r = es.verify.single("jane@acme.com")
    assert r.result == "valid"
    assert r.score == 0.95
    assert es.credits_remaining == 41
    assert es.rate_limit["limit"] == 60


def test_single_keeps_wire_field_names(monkeypatch):
    # Regression (EM-1034): snake_case wire fields survive, no camelCase rename.
    stub(monkeypatch, 200, WIRE)
    r = Emailsherlock("k").verify.single("jane@acme.com")
    assert r.catch_all is True
    assert r.mx_record == "mx1.acme.com"
    assert r.free_email is False
    assert r.checked_at == "2026-06-09T14:32:00+00:00"


def test_batch_unwraps_results_and_type_guard(monkeypatch):
    stub(monkeypatch, 200, {"results": [WIRE, {"email": "nope@", "error": "invalid_email"}]})
    resp = Emailsherlock("k").verify.batch(["jane@acme.com", "nope@"])
    assert len(resp.results) == 2
    assert is_verify_result(resp.results[0])
    assert not is_verify_result(resp.results[1])
    assert resp.results[1].error == "invalid_email"


def test_credits_returns_account_status(monkeypatch):
    stub(monkeypatch, 200, {
        "credits": {"total": 1240, "purchased": 1000, "gifted": 240},
        "rate_limit": {"limit": 60, "remaining": 59, "reset": 1700000000},
        "plan": "Free", "sandbox": False,
    })
    status = Emailsherlock("k").credits()
    assert status.credits.total == 1240
    assert status.sandbox is False


def test_submit_job_returns_processing(monkeypatch):
    stub(monkeypatch, 202, {
        "id": "job-1", "status": "processing", "total": 2,
        "progress": {"total": 2, "done": 0},
        "created_at": "2026-06-10T14:32:00+00:00", "expires_at": "2026-06-17T14:32:00+00:00",
    })
    job = Emailsherlock("k").verify.submit_job(["a@b.com", "c@d.com"])
    assert job.id == "job-1"
    assert job.status == "processing"


def test_401_raises_authentication_error(monkeypatch):
    stub(monkeypatch, 401, {"error": {"code": "unauthorized", "message": "Invalid API key."}})
    with pytest.raises(AuthenticationError) as exc:
        Emailsherlock("bad").verify.single("a@b.com")
    assert exc.value.status == 401
    assert exc.value.code == "unauthorized"


def test_402_carries_credit_headers(monkeypatch):
    stub(monkeypatch, 402,
         {"error": {"code": "insufficient_credits", "message": "Not enough credits."}},
         {"X-Credits-Required": "1", "X-Credits-Remaining": "0"})
    with pytest.raises(InsufficientCreditsError) as exc:
        Emailsherlock("k").verify.single("a@b.com")
    assert exc.value.credits_required == 1
    assert exc.value.credits_remaining == 0


def test_429_carries_retry_after(monkeypatch):
    stub(monkeypatch, 429,
         {"error": {"code": "rate_limit_exceeded", "message": "Rate limit exceeded."}},
         {"Retry-After": "30", "X-RateLimit-Limit": "60"})
    with pytest.raises(RateLimitError) as exc:
        Emailsherlock("k").verify.single("a@b.com")
    assert exc.value.retry_after == 30


def test_missing_key_raises_at_construction(monkeypatch):
    monkeypatch.delenv("ES_KEY", raising=False)
    monkeypatch.delenv("EMAILSHERLOCK_API_KEY", raising=False)
    with pytest.raises(emailsherlock.EmailsherlockError):
        Emailsherlock()


# --- X-Client-Id (EM-3857) ---------------------------------------------------

def capture_headers(monkeypatch):
    seen = []

    def _request(self, method, url, headers=None, body=None, post_params=None,
                 _request_timeout=None, **kw):
        seen.append(dict(headers or {}))
        return FakeRESTResponse(200, {
            "credits": {"total": 1240, "purchased": 1000, "gifted": 240},
            "rate_limit": {"limit": 60, "remaining": 59, "reset": 1700000000},
            "plan": "Free", "sandbox": False,
        }, None)

    monkeypatch.setattr(rest.RESTClientObject, "request", _request)
    return seen


def test_client_id_header_sent_when_set(monkeypatch):
    seen = capture_headers(monkeypatch)
    es = Emailsherlock("k", client_id=42)
    assert es.client_id == 42
    es.credits()
    assert seen[0]["X-Client-Id"] == "42"


def test_client_id_header_absent_when_unset(monkeypatch):
    seen = capture_headers(monkeypatch)
    es = Emailsherlock("k")
    assert es.client_id is None
    es.credits()
    assert "X-Client-Id" not in seen[0]


def test_with_client_id_returns_new_client(monkeypatch):
    seen = capture_headers(monkeypatch)
    base = Emailsherlock("k", base_url="https://example.test", timeout=5.0)
    tenant = base.with_client_id(7)
    assert tenant is not base
    assert tenant.client_id == 7
    assert base.client_id is None
    assert tenant._timeout == 5.0
    assert tenant._base_url == "https://example.test"
    tenant.credits()
    base.credits()
    assert seen[0]["X-Client-Id"] == "7"
    assert "X-Client-Id" not in seen[1]


@pytest.mark.parametrize("bad", [0, -1, True, "5", 1.5])
def test_invalid_client_id_raises(bad):
    with pytest.raises(emailsherlock.EmailsherlockError) as exc:
        Emailsherlock("k", client_id=bad)
    assert exc.value.code == "config_error"
    with pytest.raises(emailsherlock.EmailsherlockError):
        Emailsherlock("k").with_client_id(bad)


@pytest.mark.parametrize("status,code,cls", [
    (404, "client_not_found", emailsherlock.ValidationError),
    (400, "client_id_not_allowed", emailsherlock.ValidationError),
    (403, "forbidden", emailsherlock.ForbiddenError),
])
def test_client_errors_keep_server_code(monkeypatch, status, code, cls):
    stub(monkeypatch, status, {"error": {"code": code, "message": "x"}})
    with pytest.raises(cls) as exc:
        Emailsherlock("k", client_id=1).credits()
    assert exc.value.code == code


# --- Deliverability, DMARC, TLS-RPT, domains, impersonation (EM-4804) --------

def record(monkeypatch, status, body, headers=None):
    """Stub the REST seam and record each request's method, URL, headers and JSON body."""
    seen = []

    def _request(self, method, url, headers=None, body=None, post_params=None,
                 _request_timeout=None, **kw):
        seen.append({"method": method, "url": url, "headers": dict(headers or {}), "body": body})
        return FakeRESTResponse(status, _request.body, _request.headers)
    _request.body = body
    _request.headers = headers
    monkeypatch.setattr(rest.RESTClientObject, "request", _request)
    return seen


BASE = "https://api.emailsherlock.com"

ADDRESS = {
    "id": 45, "label": "Newsletter", "address": "dc-3f9a@check.mail.emailsherlock.com",
    "active": True, "has_webhook": False, "latest_verdict": None,
    "created_at": "2026-07-25T14:03:11+00:00",
}
CHECK = {
    "id": 90210, "address_id": 45, "address_label": "Newsletter",
    "address": "dc-3f9a@check.mail.emailsherlock.com", "received_at": "2026-07-25T14:03:11+00:00",
    "from": "news@brand.example.com", "score": 82, "verdict_band": "inbox_ready",
    "forwarded_inline": False,
}
SETUP = {
    "domain": "acme.com", "status": "not_found", "confirmed": False,
    "watch_slots": {"used": 1, "max": 3},
}
PAGE = {"limit": 10, "offset": 20, "count": 0, "next_offset": None}


def test_deliverability_list_addresses(monkeypatch):
    seen = record(monkeypatch, 200, {"addresses": [ADDRESS]})
    resp = Emailsherlock("k").deliverability.list_addresses()
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/deliverability/addresses"
    assert seen[0]["body"] is None
    assert resp.addresses[0].id == 45


def test_deliverability_latest(monkeypatch):
    seen = record(monkeypatch, 200, {
        "address_id": 45, "has_result": True,
        "verdict": {"check_id": 90210, "score": 82, "verdict_band": "inbox_ready"},
    })
    resp = Emailsherlock("k").deliverability.latest(45)
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/deliverability/addresses/45/latest"
    assert resp.verdict.score == 82


def test_deliverability_list_checks_sends_only_set_params(monkeypatch):
    seen = record(monkeypatch, 200, {
        "address_id": 45, "limit": 10, "offset": 0, "count": 0, "checks": [],
    })
    es = Emailsherlock("k")
    resp = es.deliverability.list_checks(45, limit=10)
    es.deliverability.list_checks(45)
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/deliverability/addresses/45/checks?limit=10"
    assert seen[1]["url"] == BASE + "/v1/deliverability/addresses/45/checks"
    assert resp.address_id == 45


def test_deliverability_get_check(monkeypatch):
    seen = record(monkeypatch, 200, CHECK)
    resp = Emailsherlock("k").deliverability.get_check(90210)
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/deliverability/checks/90210"
    assert resp.var_from == "news@brand.example.com"
    assert resp.verdict_band == "inbox_ready"


def test_deliverability_set_webhook_returns_secret(monkeypatch):
    seen = record(monkeypatch, 200, {
        "address_id": 45,
        "webhook": {"url": "https://hooks.example.com/es", "secret": "whsec_1"},
    })
    resp = Emailsherlock("k").deliverability.set_webhook(45, "https://hooks.example.com/es")
    assert seen[0]["method"] == "PUT"
    assert seen[0]["url"] == BASE + "/v1/deliverability/addresses/45/webhook"
    assert seen[0]["body"] == {"url": "https://hooks.example.com/es"}
    assert resp.webhook.secret == "whsec_1"


def test_deliverability_delete_webhook(monkeypatch):
    seen = record(monkeypatch, 200, {"address_id": 45, "webhook": None})
    resp = Emailsherlock("k").deliverability.delete_webhook(45)
    assert seen[0]["method"] == "DELETE"
    assert seen[0]["url"] == BASE + "/v1/deliverability/addresses/45/webhook"
    assert seen[0]["body"] is None
    assert resp.address_id == 45


def test_dmarc_start_encodes_domain(monkeypatch):
    seen = record(monkeypatch, 200, dict(SETUP, domain="bücher.de"))
    resp = Emailsherlock("k").dmarc.start("bücher.de")
    assert seen[0]["method"] == "POST"
    assert seen[0]["url"] == BASE + "/v1/domains/b%C3%BCcher.de/dmarc"
    assert resp.status == "not_found"
    assert resp.watch_slots.max == 3


def test_dmarc_check(monkeypatch):
    seen = record(monkeypatch, 200, dict(SETUP, status="found", confirmed=True))
    resp = Emailsherlock("k").dmarc.check("acme.com")
    assert seen[0]["method"] == "POST"
    assert seen[0]["url"] == BASE + "/v1/domains/acme.com/dmarc/check"
    assert resp.confirmed is True


def test_dmarc_summary(monkeypatch):
    seen = record(monkeypatch, 200, {
        "domain": "acme.com", "range_days": 7, "message_count": 120, "aligned_messages": 100,
        "aligned_pct": 83.3, "source_count": 4, "known_source_count": 3,
        "unknown_source_count": 1, "new_source_count": 0, "failing_source_count": 1,
        "last_received_at": None,
    })
    resp = Emailsherlock("k").dmarc.summary("acme.com", range=7)
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/dmarc/acme.com/summary?range=7"
    assert resp.aligned_pct == 83.3


def test_dmarc_reports_sends_from_and_to(monkeypatch):
    seen = record(monkeypatch, 200, dict(PAGE, domain="acme.com", history_from=None, reports=[]))
    resp = Emailsherlock("k").dmarc.reports(
        "acme.com", from_="2026-11-01", to=datetime.date(2026, 11, 20),
        reporter="google.com", limit=10, offset=20,
    )
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == (
        BASE + "/v1/dmarc/acme.com/reports"
        "?from=2026-11-01&to=2026-11-20&reporter=google.com&limit=10&offset=20"
    )
    assert resp.offset == 20


def test_dmarc_sources(monkeypatch):
    seen = record(monkeypatch, 200, dict(PAGE, domain="acme.com", range_days=30, sources=[]))
    resp = Emailsherlock("k").dmarc.sources("acme.com", range=30, result="fail", check="spf")
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/dmarc/acme.com/sources?range=30&result=fail&check=spf"
    assert resp.sources == []


def test_tls_rpt_reports(monkeypatch):
    seen = record(monkeypatch, 200, dict(PAGE, domain="acme.com", range_days=7, reports=[]))
    resp = Emailsherlock("k").tls_rpt.reports("acme.com", range=7, limit=10, offset=20)
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/tls-rpt/acme.com/reports?range=7&limit=10&offset=20"
    assert resp.range_days == 7


def test_domains_changes(monkeypatch):
    seen = record(monkeypatch, 200, dict(PAGE, domain="acme.com", history_from=None, changes=[{
        "type": "dkim_selector_added", "tag": "DKIM", "title": "DKIM selector added",
        "description": "", "created_at": "2026-11-20T10:00:00+00:00",
    }]))
    resp = Emailsherlock("k").domains.changes("acme.com", limit=10, offset=20)
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/domains/acme.com/changes?limit=10&offset=20"
    assert resp.changes[0].title == "DKIM selector added"


def test_domains_next_steps(monkeypatch):
    seen = record(monkeypatch, 200, {
        "domain": "acme.com", "policy": {"tag": "p", "value": "none"},
        "unaligned_sources": [], "findings": [],
    })
    resp = Emailsherlock("k").domains.next_steps("acme.com")
    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == BASE + "/v1/domains/acme.com/next-steps"
    assert resp.policy.value == "none"


ANALYZE = {
    "risk": "high", "score": 60, "identity": "Thomas Berger",
    "reasons": [{"reason": "display_name", "weight": 40, "detail": "Thomas Berger"}],
}


def test_impersonation_analyze_sends_body_and_captures_credits(monkeypatch):
    seen = record(monkeypatch, 200, ANALYZE, {"X-Credits-Remaining": "9"})
    es = Emailsherlock("k")
    resp = es.impersonation.analyze(
        "thomas.berger.ceo@gmail.com",
        [{"name": "Thomas Berger", "domains": ["acme.de"]}],
        display_name="Thomas Berger",
    )
    assert seen[0]["method"] == "POST"
    assert seen[0]["url"] == BASE + "/v1/impersonation/analyze"
    assert seen[0]["body"] == {
        "from": "thomas.berger.ceo@gmail.com",
        "display_name": "Thomas Berger",
        "protected": [{"name": "Thomas Berger", "domains": ["acme.de"]}],
    }
    assert resp.risk == "high"
    assert resp.reasons[0].weight == 40
    assert es.credits_remaining == 9


def test_impersonation_402_raises_insufficient_credits(monkeypatch):
    record(monkeypatch, 402,
           {"error": {"code": "insufficient_credits", "message": "Not enough credits."}},
           {"X-Credits-Required": "1", "X-Credits-Remaining": "0"})
    with pytest.raises(InsufficientCreditsError) as exc:
        Emailsherlock("k").impersonation.analyze("a@b.com", [{"name": "Thomas Berger"}])
    assert exc.value.status == 402
    assert exc.value.credits_required == 1


def test_dmarc_403_raises_forbidden(monkeypatch):
    record(monkeypatch, 403, {"error": {"code": "forbidden", "message": "x"}})
    with pytest.raises(emailsherlock.ForbiddenError) as exc:
        Emailsherlock("k").dmarc.summary("acme.com")
    assert exc.value.code == "forbidden"


def test_dmarc_start_409_falls_through_to_base_error(monkeypatch):
    record(monkeypatch, 409, {"error": {"code": "conflict", "message": "x"}})
    with pytest.raises(emailsherlock.EmailsherlockError) as exc:
        Emailsherlock("k").dmarc.start("acme.com")
    assert type(exc.value) is emailsherlock.EmailsherlockError
    assert exc.value.status == 409
    assert exc.value.code == "conflict"


def test_client_id_reaches_new_endpoint(monkeypatch):
    seen = record(monkeypatch, 200, dict(PAGE, domain="acme.com", history_from=None, changes=[]))
    base = Emailsherlock("k")
    base.with_client_id(42).domains.changes("acme.com")
    base.domains.changes("acme.com")
    assert seen[0]["headers"]["X-Client-Id"] == "42"
    assert "X-Client-Id" not in seen[1]["headers"]


# --- EM-4987: balance headers, client-side validation codes -----------------


def test_reads_both_balances_from_their_current_headers(monkeypatch):
    # The alias X-Credits-Remaining carries another value on purpose, so the
    # test fails if the client still reads the alias first.
    stub(monkeypatch, 200, WIRE, {
        "X-Probe-Credits-Remaining": "41", "X-Credits-Remaining": "7",
        "X-Validations-Remaining": "950", "X-Verify-Free-Remaining": "3",
    })
    es = Emailsherlock("k")
    es.verify.single("jane@acme.com")
    assert es.probe_credits_remaining == 41
    assert es.validations_remaining == 950
    assert es.credits_remaining == 41


def test_falls_back_to_the_legacy_balance_headers(monkeypatch):
    stub(monkeypatch, 200, WIRE, {"X-Credits-Remaining": "12", "X-Verify-Free-Remaining": "30"})
    es = Emailsherlock("k")
    es.verify.single("jane@acme.com")
    assert es.probe_credits_remaining == 12
    assert es.validations_remaining == 30
    assert es.credits_remaining == 12


def test_validations_stay_none_when_the_plan_is_unlimited(monkeypatch):
    stub(monkeypatch, 200, WIRE, {"X-Probe-Credits-Remaining": "41"})
    es = Emailsherlock("k")
    es.verify.single("jane@acme.com")
    assert es.validations_remaining is None
    assert es.probe_credits_remaining == 41


def test_402_prefers_the_probe_credits_header(monkeypatch):
    stub(monkeypatch, 402,
         {"error": {"code": "insufficient_credits", "message": "Not enough credits."}},
         {"X-Probe-Credits-Remaining": "2", "X-Credits-Remaining": "9"})
    with pytest.raises(InsufficientCreditsError) as exc:
        Emailsherlock("k").verify.single("a@b.com")
    assert exc.value.credits_remaining == 2


def test_bad_argument_raises_invalid_argument_without_a_request(monkeypatch):
    seen = record(monkeypatch, 200, {"address_id": 45, "limit": 10, "offset": 0, "count": 0, "checks": []})
    with pytest.raises(emailsherlock.EmailsherlockError) as exc:
        Emailsherlock("k").deliverability.list_checks(45, limit=0)
    assert exc.value.code == "invalid_argument"
    assert seen == []


def test_protected_entry_without_name_raises_invalid_argument(monkeypatch):
    seen = record(monkeypatch, 200, ANALYZE)
    with pytest.raises(emailsherlock.EmailsherlockError) as exc:
        Emailsherlock("k").impersonation.analyze("a@b.com", [{"domains": ["acme.de"]}])
    assert exc.value.code == "invalid_argument"
    assert seen == []


def test_response_the_models_refuse_raises_invalid_response(monkeypatch):
    # An enum value newer than this SDK version: pydantic refuses it while the
    # response is read. That is not a network failure and not a bad argument.
    stub(monkeypatch, 200, {**WIRE, "result": "quarantined"}, {"X-Probe-Credits-Remaining": "41"})
    es = Emailsherlock("k")
    with pytest.raises(emailsherlock.EmailsherlockError) as exc:
        es.verify.single("jane@acme.com")
    assert exc.value.code == "invalid_response"
    assert es.probe_credits_remaining == 41
