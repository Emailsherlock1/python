"""Typed result objects returned by the client."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


def _opt_bool(value: Any) -> Optional[bool]:
    return None if value is None else bool(value)


def _opt_float(value: Any) -> Optional[float]:
    return None if value is None else float(value)


def _opt_int(value: Any) -> Optional[int]:
    return None if value is None else int(value)


@dataclass
class VerifyDomain:
    """Domain-level intelligence attached to a verify result.

    All attributes except ``name`` are optional: the API returns ``null``
    when a signal has not been measured for the domain yet.
    """

    name: str
    types: Optional[List[str]] = None  # freemail | disposable | custom | company | government | education | public | isp
    score: Optional[float] = None  # 0-100 domain trust score
    spf: Optional[bool] = None
    dkim: Optional[bool] = None
    dmarc: Optional[bool] = None
    dmarc_policy: Optional[str] = None  # none | quarantine | reject
    mta_sts: Optional[bool] = None
    tls_rpt: Optional[bool] = None
    bimi: Optional[bool] = None
    dane: Optional[bool] = None
    blacklists: Optional[int] = None  # number of DNSBL listings
    dnssec: Optional[str] = None  # secure | insecure | bogus
    caa: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerifyDomain":
        types = data.get("types")
        return cls(
            name=data.get("name", ""),
            types=list(types) if types is not None else None,
            score=_opt_float(data.get("score")),
            spf=_opt_bool(data.get("spf")),
            dkim=_opt_bool(data.get("dkim")),
            dmarc=_opt_bool(data.get("dmarc")),
            dmarc_policy=data.get("dmarc_policy"),
            mta_sts=_opt_bool(data.get("mta_sts")),
            tls_rpt=_opt_bool(data.get("tls_rpt")),
            bimi=_opt_bool(data.get("bimi")),
            dane=_opt_bool(data.get("dane")),
            blacklists=_opt_int(data.get("blacklists")),
            dnssec=data.get("dnssec"),
            caa=_opt_bool(data.get("caa")),
        )


@dataclass
class VerifyResult:
    """The result for one verified address. Mirrors the API JSON.

    ``score`` is ``None`` when the API could not compute a confidence,
    e.g. for ``unknown`` results. The v2 fields (``deliverable`` through
    ``domain``) are ``None`` when the API does not return them.
    """

    email: str
    result: str  # valid | invalid | catch_all | disposable | role | unknown
    mx: bool
    disposable: bool
    role: bool
    catch_all: bool
    score: Optional[float]
    freshness: str  # fresh | cached_recent | cached_stale_refreshed
    deliverable: Optional[bool] = None
    reason: Optional[str] = None  # bad_syntax | no_mx | mailbox_accepts | mailbox_not_found | disposable_provider | role_address | catch_all_domain | greylisted | smtp_timeout | smtp_unreachable | verification_pending
    mx_record: Optional[str] = None
    free_email: Optional[bool] = None
    checked_at: Optional[str] = None  # ISO 8601
    domain: Optional[VerifyDomain] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerifyResult":
        domain = data.get("domain")
        return cls(
            email=data.get("email", ""),
            result=data.get("result", "unknown"),
            mx=bool(data.get("mx", False)),
            disposable=bool(data.get("disposable", False)),
            role=bool(data.get("role", False)),
            catch_all=bool(data.get("catch_all", False)),
            score=_opt_float(data.get("score")),
            freshness=data.get("freshness", ""),
            deliverable=_opt_bool(data.get("deliverable")),
            reason=data.get("reason"),
            mx_record=data.get("mx_record"),
            free_email=_opt_bool(data.get("free_email")),
            checked_at=data.get("checked_at"),
            domain=VerifyDomain.from_dict(domain) if isinstance(domain, dict) else None,
            raw=data,
        )


@dataclass
class BatchItemError:
    """A per-address failure inside a batch response."""

    email: Optional[str]
    error: str  # invalid_email | insufficient_credits | verify_unavailable

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchItemError":
        return cls(email=data.get("email"), error=data.get("error", "unknown"))


BatchItem = Union[VerifyResult, BatchItemError]


@dataclass
class BatchResponse:
    """The response of a batch call: a list of results and/or per-item errors."""

    results: List[BatchItem]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchResponse":
        items: List[BatchItem] = []
        for item in data.get("results", []):
            if isinstance(item, dict) and "error" in item:
                items.append(BatchItemError.from_dict(item))
            else:
                items.append(VerifyResult.from_dict(item))
        return cls(results=items)
