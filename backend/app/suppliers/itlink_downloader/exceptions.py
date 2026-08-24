"""
Custom exceptions for the IT-Link price list downloader.
"""


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class AuthenticationError(Exception):
    """Raised when authentication with IT-Link fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class DownloadError(Exception):
    """Raised when downloading the price list fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)