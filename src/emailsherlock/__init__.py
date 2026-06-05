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
from .models import BatchItemError, BatchResponse, VerifyResult

__all__ = [
    "__version__",
    "Emailsherlock",
    "VerifyResult",
    "BatchResponse",
    "BatchItemError",
    "EmailsherlockError",
    "AuthenticationError",
    "ForbiddenError",
    "InsufficientCreditsError",
    "RateLimitError",
    "ValidationError",
    "ServiceUnavailableError",
]
