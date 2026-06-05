"""Typed result objects returned by the client."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class VerifyResult:
    """The result for one verified address. Mirrors the API JSON."""

    email: str
    result: str  # valid | invalid | catch_all | disposable | role | unknown
    mx: bool
    disposable: bool
    role: bool
    catch_all: bool
    score: float
    freshness: str  # fresh | cached_recent | cached_stale_refreshed
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerifyResult":
        return cls(
            email=data.get("email", ""),
            result=data.get("result", "unknown"),
            mx=bool(data.get("mx", False)),
            disposable=bool(data.get("disposable", False)),
            role=bool(data.get("role", False)),
            catch_all=bool(data.get("catch_all", False)),
            score=float(data.get("score", 0.0)),
            freshness=data.get("freshness", ""),
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
