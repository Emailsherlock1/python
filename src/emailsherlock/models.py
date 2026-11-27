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
from emailsherlock._generated.models.deliverability_address_resource import DeliverabilityAddressResource
from emailsherlock._generated.models.deliverability_check_resource import DeliverabilityCheckResource
from emailsherlock._generated.models.deliverability_latest_verdict_resource import DeliverabilityLatestVerdictResource
from emailsherlock._generated.models.deliverability_webhook_resource import DeliverabilityWebhookResource
from emailsherlock._generated.models.dmarc_report_resource import DmarcReportResource
from emailsherlock._generated.models.dmarc_setup_resource import DmarcSetupResource
from emailsherlock._generated.models.dmarc_source_resource import DmarcSourceResource
from emailsherlock._generated.models.dmarc_summary_resource import DmarcSummaryResource
from emailsherlock._generated.models.domain_change_resource import DomainChangeResource
from emailsherlock._generated.models.get_check200_response import GetCheck200Response
from emailsherlock._generated.models.impersonation_analyze_response import ImpersonationAnalyzeResponse
from emailsherlock._generated.models.list_check_addresses200_response import ListCheckAddresses200Response
from emailsherlock._generated.models.list_checks200_response import ListChecks200Response
from emailsherlock._generated.models.list_dmarc_reports200_response import ListDmarcReports200Response
from emailsherlock._generated.models.list_dmarc_sources200_response import ListDmarcSources200Response
from emailsherlock._generated.models.list_domain_changes200_response import ListDomainChanges200Response
from emailsherlock._generated.models.list_tls_rpt_reports200_response import ListTlsRptReports200Response
from emailsherlock._generated.models.next_steps_resource import NextStepsResource
from emailsherlock._generated.models.tls_rpt_report_resource import TlsRptReportResource
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
    "DeliverabilityAddressResource",
    "DeliverabilityCheckResource",
    "DeliverabilityLatestVerdictResource",
    "DeliverabilityWebhookResource",
    "DmarcReportResource",
    "DmarcSetupResource",
    "DmarcSourceResource",
    "DmarcSummaryResource",
    "DomainChangeResource",
    "GetCheck200Response",
    "ImpersonationAnalyzeResponse",
    "ListCheckAddresses200Response",
    "ListChecks200Response",
    "ListDmarcReports200Response",
    "ListDmarcSources200Response",
    "ListDomainChanges200Response",
    "ListTlsRptReports200Response",
    "NextStepsResource",
    "TlsRptReportResource",
]
