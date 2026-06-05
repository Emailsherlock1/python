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
