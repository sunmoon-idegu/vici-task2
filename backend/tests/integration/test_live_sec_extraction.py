"""Optional end-to-end tests against exact SEC filing URLs."""

import os
import unittest

from app.controllers.extraction_controller import ExtractionController
from app.repositories.sec_filing_repository import SecFilingRepository
from app.schemas.extraction_schema import ExtractionRequest
from app.services.extraction.extraction_service import ExtractionService


MODERN_URL = (
    "https://www.sec.gov/Archives/edgar/data/21344/"
    "000162828026010047/ko-20251231.htm"
)
HISTORICAL_URL = (
    "https://www.sec.gov/Archives/edgar/data/21344/"
    "0000021344-95-000007.txt"
)
MODERN_ITEMS = [
    "1",
    "1A",
    "1B",
    "1C",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "7A",
    "8",
    "9",
    "9A",
    "9B",
    "9C",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
]
HISTORICAL_ITEMS = [str(number) for number in range(1, 15)]


@unittest.skipUnless(
    os.environ.get("RUN_SEC_INTEGRATION_TESTS") == "1",
    "set RUN_SEC_INTEGRATION_TESTS=1 to access SEC",
)
class LiveSecExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = ExtractionController(
            repository=SecFilingRepository(),
            service=ExtractionService(),
        )

    def _extract(self, url: str):
        return self.controller.extract(ExtractionRequest(url=url))

    def test_modern_html(self) -> None:
        response = self._extract(MODERN_URL)
        self.assertEqual(
            [item.item for item in response.items],
            MODERN_ITEMS,
        )
        self.assertGreaterEqual(response.confidence, 0.90)
        item_2 = next(item for item in response.items if item.item == "2")
        self.assertIn("<table>", item_2.content_html)

    def test_historical_complete_submission_txt(self) -> None:
        response = self._extract(HISTORICAL_URL)
        self.assertEqual(
            [item.item for item in response.items],
            HISTORICAL_ITEMS,
        )
        self.assertGreaterEqual(response.confidence, 0.90)
        self.assertIn("EXHIBITS", response.items[-1].title)
