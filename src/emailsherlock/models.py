"""Result objects.

The wire models are generated from the OpenAPI spec and live in
``emailsherlock._generated.models``. This module re-exports them under the
package's public names and keeps the v0.1.0 aliases (``VerifyResult``,
``BatchResponse``) working.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Union

from emailsherlock._generated.models.account_status_response import AccountStatusResponse
from emailsherlock._generated.models.batch_item_error import BatchItemError
from emailsherlock._generated.models.verify_decision_response import VerifyDecisionResponse
from emailsherlock._generated.models.verify_domain_response import VerifyDomainResponse
from emailsherlock._generated.models.verify_job_response import VerifyJobResponse
from emailsherlock._generated.models.verify_result_response import VerifyResultResponse

# v0.1.0 compatibility alias: the single-verify result kept the name VerifyResult.
VerifyResult = VerifyResultResponse

#: A batch entry is either a full result or a per-address error.
BatchItem = Union[VerifyResultResponse, BatchItemError]


@dataclass
class BatchResponse:
    """The response of a batch call: results and/or per-item errors, in order.

    Mirrors the v0.1.0 shape (``.results`` is a flat list of unwrapped entries),
    rather than exposing the generated oneOf wrapper.
    """

    results: List[BatchItem]


def is_verify_result(item: BatchItem) -> bool:
    """Type guard for a batch entry: did this address verify, or fail?"""
    return isinstance(item, VerifyResultResponse)


__all__ = [
    "VerifyResult",
    "VerifyResultResponse",
    "BatchItemError",
    "BatchResponse",
    "BatchItem",
    "is_verify_result",
    "VerifyJobResponse",
    "VerifyDomainResponse",
    "VerifyDecisionResponse",
    "AccountStatusResponse",
]
