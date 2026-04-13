"""Bot module for automated job applications."""

from .engine import ApplicationBot
from .captcha import CaptchaSolver
from .autofill import AutoFiller
from .gmail import GmailVerificationHandler

__all__ = [
    "ApplicationBot",
    "CaptchaSolver",
    "AutoFiller",
    "GmailVerificationHandler",
]
