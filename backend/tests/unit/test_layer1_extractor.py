"""Tests for Layer 1 extraction without external I/O."""

import unittest

from app.models.filing_document import FilingDocument
from app.services.extraction.extractors.layer1_extractor import (
    Layer1Extractor,
    filing_confidence,
    select_10k_document,
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

    def test_selects_10ksb_document_from_submission(self) -> None:
        submission = """
        <DOCUMENT>
        <TYPE>EX-21
        <TEXT>Exhibit content</TEXT>
        </DOCUMENT>
        <DOCUMENT>
        <TYPE>10KSB
        <TEXT>ITEM 1. DESCRIPTION OF BUSINESS
        Filing content
        ITEM 8A. CONTROLS AND PROCEDURES
        Control content
        </TEXT>
        </DOCUMENT>
        """

        document, form_type = select_10k_document(submission)

        self.assertEqual(form_type, "10KSB")
        self.assertIn("ITEM 1. DESCRIPTION OF BUSINESS", document)
        self.assertIn("ITEM 8A. CONTROLS AND PROCEDURES", document)
