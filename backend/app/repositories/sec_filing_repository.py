"""SEC filing data access and preparation."""

from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.config import Settings, settings
from app.core.exceptions import FilingDownloadError, InvalidFilingUrlError
from app.models.filing_document import FilingDocument


class SecFilingRepository:
    """Fetch supported filings from the official SEC Archives."""

    def __init__(
        self,
        config: Settings = settings,
        opener: Callable = urlopen,
    ) -> None:
        self.config = config
        self.opener = opener

    @staticmethod
    def validate_url(url: str) -> None:
        parsed = urlparse(url)
        path = parsed.path.lower()
        if (
            parsed.scheme != "https"
            or parsed.hostname != "www.sec.gov"
            or not path.startswith("/archives/edgar/data/")
            or not path.endswith((".htm", ".html", ".txt"))
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise InvalidFilingUrlError(
                "URL must be an HTTPS SEC Archives filing document"
            )

    def fetch(self, url: str) -> FilingDocument:
        self.validate_url(url)
        request = Request(
            url,
            headers={
                "User-Agent": self.config.sec_user_agent,
                "Accept-Encoding": "identity",
                "Accept": (
                    "text/html,application/xhtml+xml,text/plain;q=0.9,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.sec.gov/edgar/search/",
            },
        )

        try:
            with self.opener(
                request,
                timeout=self.config.sec_timeout_seconds,
            ) as response:
                final_url = response.geturl()
                self.validate_url(final_url)
                content = response.read()
                content_type = response.headers.get_content_type()
        except InvalidFilingUrlError:
            raise
        except (HTTPError, URLError, OSError) as exc:
            raise FilingDownloadError(
                f"Unable to download SEC filing: {exc}"
            ) from exc

        document_type = (
            "txt"
            if urlparse(final_url).path.lower().endswith(".txt")
            or content_type == "text/plain"
            else "html"
        )
        return FilingDocument(
            content=content,
            document_type=document_type,
        )
