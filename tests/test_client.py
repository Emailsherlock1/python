"""Unit tests with a stubbed urlopen. No network."""
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import emailsherlock
from emailsherlock import (
    AuthenticationError,
    Emailsherlock,
    InsufficientCreditsError,
    RateLimitError,
    VerifyDomain,
    VerifyResult,
    BatchItemError,
)


class FakeHeaders(dict):
    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


class FakeResponse:
    def __init__(self, status, body, headers):
        self.status = status
        self._body = json.dumps(body).encode()
        self.headers = FakeHeaders(headers)

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def patch(monkeypatch, status, body, headers=None):
    headers = headers or {}
    if status >= 400:
        def raiser(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, status, "err", FakeHeaders(headers),
                io.BytesIO(json.dumps(body).encode()),
            )
        monkeypatch.setattr(emailsherlock.client.urllib.request, "urlopen", raiser)
    else:
        monkeypatch.setattr(
            emailsherlock.client.urllib.request,
            "urlopen",
            lambda req, timeout=None: FakeResponse(status, body, headers),
        )


def test_single_ok(monkeypatch):
    patch(
        monkeypatch, 200,
        {"email": "jane@acme.com", "result": "valid", "mx": True, "disposable": False,
         "role": False, "catch_all": False, "score": 0.95, "freshness": "fresh"},
        {"X-Credits-Remaining": "41", "X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "59", "X-RateLimit-Reset": "1700000000"},
    )
    es = Emailsherlock("k")
    result = es.verify.single("jane@acme.com")
    assert isinstance(result, VerifyResult)
    assert result.result == "valid"
    assert result.score == 0.95
    assert es.credits_remaining == 41
    assert es.rate_limit["limit"] == 60


def test_single_score_null(monkeypatch):
    # the API returns score: null for unknown results (e.g. sandbox unknown@)
    patch(
        monkeypatch, 200,
        {"email": "unknown@acme.com", "result": "unknown", "mx": True, "disposable": False,
         "role": False, "catch_all": False, "score": None, "freshness": "fresh"},
    )
    es = Emailsherlock("k")
    result = es.verify.single("unknown@acme.com")
    assert result.result == "unknown"
    assert result.score is None


def test_v2_fields_absent_default_to_none():
    # pre-v2 API responses do not carry the new fields
    result = VerifyResult.from_dict(
        {"email": "jane@acme.com", "result": "valid", "mx": True, "disposable": False,
         "role": False, "catch_all": False, "score": 0.95, "freshness": "fresh"}
    )
    assert result.deliverable is None
    assert result.reason is None
    assert result.mx_record is None
    assert result.free_email is None
    assert result.checked_at is None
    assert result.domain is None


def test_v2_fields_and_domain_parsing(monkeypatch):
    patch(
        monkeypatch, 200,
        {"email": "jane@acme.com", "result": "valid", "mx": True, "disposable": False,
         "role": False, "catch_all": False, "score": 0.95, "freshness": "fresh",
         "deliverable": True, "reason": "mailbox_accepts", "mx_record": "mx1.acme.com",
         "free_email": False, "checked_at": "2026-06-09T12:00:00Z",
         "domain": {
             "name": "acme.com", "types": ["company"], "score": 87,
             "spf": True, "dkim": True, "dmarc": True, "dmarc_policy": "reject",
             "mta_sts": False, "tls_rpt": None, "bimi": False, "dane": None,
             "blacklists": 0, "dnssec": "secure", "caa": True,
         }},
    )
    es = Emailsherlock("k")
    result = es.verify.single("jane@acme.com")
    assert result.deliverable is True
    assert result.reason == "mailbox_accepts"
    assert result.mx_record == "mx1.acme.com"
    assert result.free_email is False
    assert result.checked_at == "2026-06-09T12:00:00Z"
    assert isinstance(result.domain, VerifyDomain)
    assert result.domain.name == "acme.com"
    assert result.domain.types == ["company"]
    assert result.domain.score == 87.0
    assert result.domain.dmarc_policy == "reject"
    assert result.domain.tls_rpt is None
    assert result.domain.dane is None
    assert result.domain.blacklists == 0
    assert result.domain.dnssec == "secure"
    assert result.domain.caa is True
    assert result.raw["domain"]["name"] == "acme.com"


def test_domain_all_nullable_fields_null():
    domain = VerifyDomain.from_dict({"name": "acme.com"})
    assert domain.name == "acme.com"
    assert domain.types is None
    assert domain.score is None
    assert domain.spf is None
    assert domain.dnssec is None
    assert domain.caa is None


def test_batch_mixed(monkeypatch):
    patch(monkeypatch, 200, {"results": [
        {"email": "jane@acme.com", "result": "valid", "mx": True, "disposable": False, "role": False, "catch_all": False, "score": 0.9, "freshness": "fresh"},
        {"email": "nope@", "error": "invalid_email"},
    ]})
    es = Emailsherlock("k")
    batch = es.verify.batch(["jane@acme.com", "nope@"])
    assert len(batch.results) == 2
    assert isinstance(batch.results[0], VerifyResult)
    assert isinstance(batch.results[1], BatchItemError)
    assert batch.results[1].error == "invalid_email"


def test_401(monkeypatch):
    patch(monkeypatch, 401, {"error": {"code": "unauthorized", "message": "Invalid API key."}})
    es = Emailsherlock("bad")
    with pytest.raises(AuthenticationError) as exc:
        es.verify.single("a@b.com")
    assert exc.value.status == 401
    assert exc.value.code == "unauthorized"


def test_402(monkeypatch):
    patch(monkeypatch, 402, {"error": {"code": "insufficient_credits", "message": "Not enough."}},
          {"X-Credits-Required": "1", "X-Credits-Remaining": "0"})
    es = Emailsherlock("k")
    with pytest.raises(InsufficientCreditsError) as exc:
        es.verify.single("a@b.com")
    assert exc.value.credits_required == 1
    assert exc.value.credits_remaining == 0


def test_429(monkeypatch):
    patch(monkeypatch, 429, {"error": {"code": "rate_limit_exceeded", "message": "Slow down."}},
          {"Retry-After": "30"})
    es = Emailsherlock("k")
    with pytest.raises(RateLimitError) as exc:
        es.verify.single("a@b.com")
    assert exc.value.retry_after == 30


def test_missing_key(monkeypatch):
    monkeypatch.delenv("ES_KEY", raising=False)
    monkeypatch.delenv("EMAILSHERLOCK_API_KEY", raising=False)
    with pytest.raises(emailsherlock.EmailsherlockError):
        Emailsherlock()
