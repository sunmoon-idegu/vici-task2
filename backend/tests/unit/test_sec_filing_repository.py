"""Tests for SEC repository validation and document preparation."""

from email.message import Message
import unittest

from app.core.exceptions import InvalidFilingUrlError
from app.repositories.sec_filing_repository import SecFilingRepository


SEC_URL = (
    "https://www.sec.gov/Archives/edgar/data/21344/"
    "000162828026010047/ko-20251231.htm"
)


class FakeResponse:
    def __init__(self, content: bytes, url: str, content_type: str) -> None:
        self.content = content
        self.url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def geturl(self) -> str:
        return self.url

    def read(self) -> bytes:
        return self.content


class SecFilingRepositoryTests(unittest.TestCase):
    def test_rejects_non_sec_url(self) -> None:
        repository = SecFilingRepository()
        with self.assertRaises(InvalidFilingUrlError):
            repository.fetch("https://example.com/filing.htm")

    def test_fetch_prepares_html_document(self) -> None:
        def opener(request, timeout):
            return FakeResponse(
                b"<html><body>10-K</body></html>",
                SEC_URL,
                "text/html",
            )

        document = SecFilingRepository(opener=opener).fetch(SEC_URL)

        self.assertEqual(document.document_type, "html")
        self.assertIn(b"10-K", document.content)
