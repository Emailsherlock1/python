"""Official Python client for the EmailSherlock email-verification API."""
from ._version import __version__
from .client import Emailsherlock
from .errors import (
    AuthenticationError,
    EmailsherlockError,
    ForbiddenError,
    InsufficientCreditsError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
)
from .models import (
    AccountStatusResponse,
    BatchItem,
    BatchItemError,
    BatchResponse,
    VerifyDecisionResponse,
    VerifyDomainResponse,
    VerifyJobResponse,
    VerifyResult,
    VerifyResultResponse,
    is_verify_result,
)

__all__ = [
    "__version__",
    "Emailsherlock",
    "VerifyResult",
    "VerifyResultResponse",
    "VerifyJobResponse",
    "VerifyDomainResponse",
    "VerifyDecisionResponse",
    "AccountStatusResponse",
    "BatchResponse",
    "BatchItem",
    "BatchItemError",
    "is_verify_result",
    "EmailsherlockError",
    "AuthenticationError",
    "ForbiddenError",
    "InsufficientCreditsError",
    "RateLimitError",
    "ValidationError",
    "ServiceUnavailableError",
]
