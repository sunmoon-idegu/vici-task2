"""Application-specific exceptions."""


class BackendError(Exception):
    """Base class for expected backend errors."""


class InvalidFilingUrlError(BackendError):
    """The supplied URL is not a supported SEC filing URL."""


class FilingDownloadError(BackendError):
    """The SEC filing could not be downloaded."""


class FilingExtractionError(BackendError):
    """The downloaded document could not be extracted."""
