"""Unit tests with a stubbed REST layer. No network.

The client wraps the generated urllib3-based raw client, so we stub
``RESTClientObject.request`` (the single HTTP seam) rather than urllib.
"""
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
