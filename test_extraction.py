"""Unit and optional live SEC tests for Layer 1 extraction."""

from __future__ import annotations

import os
import unittest

from evaluation import HeadingCandidate, calculate_heading_confidence
from extraction import extract_items, extract_items_from_bytes, filing_confidence


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


class EvaluationTests(unittest.TestCase):
    def test_standard_heading(self) -> None:
        candidate = HeadingCandidate(
            text="ITEM 1A. RISK FACTORS",
            expected_item="1A",
            expected_title="Risk Factors",
            is_own_dom_block=True,
        )
        self.assertEqual(calculate_heading_confidence(candidate), 1.0)

    def test_subitem_is_not_a_main_item_heading(self) -> None:
        candidate = HeadingCandidate(
            text="ITEM 14(a)2",
            expected_item="14",
        )
        self.assertEqual(calculate_heading_confidence(candidate), 0.0)


class LocalExtractionTests(unittest.TestCase):
    def test_html_toc_is_not_selected(self) -> None:
        document = b"""
        <html><body>
          <table>
            <tr><td><a href="#i1">Item 1. Business</a></td><td>3</td></tr>
            <tr><td><a href="#i2">Item 2. Properties</a></td><td>8</td></tr>
          </table>
          <div><b>ITEM 1. BUSINESS</b></div>
          <p>""" + b"A" * 600 + b"""</p>
          <div><b>ITEM 2. PROPERTIES</b></div>
          <p>""" + b"B" * 600 + b"""</p>
          <div>SIGNATURES</div>
        </body></html>
        """
        items = extract_items_from_bytes(document, document_type="html")
        self.assertEqual([item["item"] for item in items], ["1", "2"])
        self.assertEqual(filing_confidence(items), 1.0)
        self.assertIn("<p>", items[0]["content_html"])


@unittest.skipUnless(
    os.environ.get("RUN_SEC_INTEGRATION_TESTS") == "1",
    "set RUN_SEC_INTEGRATION_TESTS=1 to access SEC",
)
class LiveSecExtractionTests(unittest.TestCase):
    def _assert_result(
        self,
        url: str,
        expected_items: list,
        minimum_confidence: float,
    ) -> list:
        items = extract_items(url)
        self.assertEqual([item["item"] for item in items], expected_items)
        self.assertGreaterEqual(filing_confidence(items), minimum_confidence)
        for item in items:
            self.assertLess(item["start"], item["end"])
            self.assertTrue(item["content"])
            self.assertTrue(item["content_html"])
            self.assertEqual(
                set(item["confidence"]),
                {"score", "heading", "body_vs_toc", "section"},
            )
        return items

    def test_modern_html(self) -> None:
        items = self._assert_result(MODERN_URL, MODERN_ITEMS, 0.90)
        item_2 = next(item for item in items if item["item"] == "2")
        self.assertIn("<table>", item_2["content_html"])

    def test_historical_complete_submission_txt(self) -> None:
        items = self._assert_result(
            HISTORICAL_URL,
            HISTORICAL_ITEMS,
            0.90,
        )
        item_14 = items[-1]
        self.assertIn("EXHIBITS", item_14["title"])
        self.assertNotEqual(item_14["title"], "(a)2")


if __name__ == "__main__":
    unittest.main()
