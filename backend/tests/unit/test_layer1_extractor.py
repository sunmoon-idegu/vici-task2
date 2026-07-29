"""Tests for Layer 1 extraction without external I/O."""

import unittest

from app.models.filing_document import FilingDocument
from app.services.extraction.extractors.layer1_extractor import (
    Layer1Extractor,
    filing_confidence,
)


class Layer1ExtractorTests(unittest.TestCase):
    def test_html_toc_is_not_selected(self) -> None:
        content = b"""
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
        items = Layer1Extractor().extract(
            FilingDocument(content=content, document_type="html")
        )

        self.assertEqual([item["item"] for item in items], ["1", "2"])
        self.assertEqual(filing_confidence(items), 1.0)
        self.assertIn("<p>", items[0]["content_html"])

    def test_invalid_document_type_fails(self) -> None:
        with self.assertRaises(ValueError):
            Layer1Extractor().extract(
                FilingDocument(content=b"", document_type="pdf")
            )
