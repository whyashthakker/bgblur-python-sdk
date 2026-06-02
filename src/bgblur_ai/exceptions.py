"""Exception types raised by the bgblur_ai SDK."""


class PrivacyBlurError(Exception):
    """Base exception for SDK errors."""


class AuthenticationError(PrivacyBlurError):
    """Raised when the API rejects the supplied credentials."""


class RateLimitError(PrivacyBlurError):
    """Raised when the API rate limit is exceeded."""


class ServerError(PrivacyBlurError):
    """Raised when the API returns a server-side failure."""
