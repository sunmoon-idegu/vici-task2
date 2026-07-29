"""Tests for Layer 2 LLM re-extraction, without any network access."""

import json
import unittest

from app.core.exceptions import LLMDisambiguationError
from app.evaluations.confidence_evaluator import ITEM_HEADING_RE
from app.models.filing_document import FilingDocument
from app.services.extraction.extractors.layer1_extractor import (
    normalize_html_document,
)
from app.services.extraction.extractors.layer2_extractor import (
    Layer2Extractor,
)


HTML_WITH_TOC = (
    b"""
    <html><body>
      <table>
        <tr><td><a href="#i1">Item 1. Business</a></td><td>3</td></tr>
        <tr><td><a href="#i2">Item 2. Properties</a></td><td>8</td></tr>
      </table>
      <div><b>ITEM 1. BUSINESS</b></div>
      <p>"""
    + b"A" * 600
    + b"""</p>
      <div><b>ITEM 2. PROPERTIES</b></div>
      <p>"""
    + b"B" * 600
    + b"""</p>
      <div>SIGNATURES</div>
    </body></html>
    """
)


def _heading_block_indexes(html: bytes) -> dict:
    """Map item -> {'toc': index, 'body': index} by scanning all blocks."""

    normalized = normalize_html_document(html)
    result: dict = {}
    for index, block in enumerate(normalized.blocks):
        match = ITEM_HEADING_RE.match(block.text)
        if not match:
            continue
        item = match.group("item").upper()
        kind = "toc" if block.is_only_html_link else "body"
        result.setdefault(item, {})[kind] = index
    return result


class FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class FakeUsage:
    def __init__(self, input_tokens: int = 100, output_tokens: int = 20) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.content = [FakeTextBlock(json.dumps(payload))]
        self.usage = FakeUsage()


class FakeMessages:
    def __init__(self, payload=None, error=None) -> None:
        self.payload = payload
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeResponse(self.payload)


class FakeClient:
    def __init__(self, payload=None, error=None) -> None:
        self.messages = FakeMessages(payload=payload, error=error)


def _items_payload(item_to_block_index: dict) -> dict:
    return {
        "items": [
            {"item": item, "block_index": index}
            for item, index in item_to_block_index.items()
        ]
    }


class Layer2ExtractorTests(unittest.TestCase):
    def test_llm_selects_body_heading_over_toc_entry(self) -> None:
        indexes = _heading_block_indexes(HTML_WITH_TOC)
        client = FakeClient(
            payload=_items_payload(
                {"1": indexes["1"]["body"], "2": indexes["2"]["body"]}
            )
        )
        extractor = Layer2Extractor(client=client, model="claude-haiku-4-5")

        items = extractor.extract(
            FilingDocument(content=HTML_WITH_TOC, document_type="html")
        )

        self.assertEqual([item["item"] for item in items], ["1", "2"])
        self.assertIn("AAAA", items[0]["content"])
        self.assertIn("BBBB", items[1]["content"])
        self.assertEqual(len(client.messages.calls), 1)

    def test_full_heading_text_as_item_field_is_still_recognized(self) -> None:
        """Regression test: the model sometimes returns the full heading
        text (e.g. "ITEM 1A. RISK FACTORS") instead of a bare code. The
        parser must still recognize it rather than silently dropping the
        item."""

        indexes = _heading_block_indexes(HTML_WITH_TOC)
        client = FakeClient(
            payload=_items_payload(
                {
                    "ITEM 1. BUSINESS": indexes["1"]["body"],
                    "Item 2. Properties": indexes["2"]["body"],
                }
            )
        )
        extractor = Layer2Extractor(client=client)

        items = extractor.extract(
            FilingDocument(content=HTML_WITH_TOC, document_type="html")
        )

        self.assertEqual([item["item"] for item in items], ["1", "2"])

    def test_program_honors_whatever_block_the_model_names(self) -> None:
        indexes = _heading_block_indexes(HTML_WITH_TOC)
        client = FakeClient(
            payload=_items_payload(
                {"1": indexes["1"]["toc"], "2": indexes["2"]["toc"]}
            )
        )
        extractor = Layer2Extractor(client=client)

        items = extractor.extract(
            FilingDocument(content=HTML_WITH_TOC, document_type="html")
        )

        self.assertIn("Item 1. Business", items[0]["content"])
        self.assertNotIn("AAAA", items[0]["content"])

    def test_out_of_range_block_index_is_dropped(self) -> None:
        indexes = _heading_block_indexes(HTML_WITH_TOC)
        client = FakeClient(
            payload=_items_payload({"1": 9999, "2": indexes["2"]["body"]})
        )
        extractor = Layer2Extractor(client=client)

        items = extractor.extract(
            FilingDocument(content=HTML_WITH_TOC, document_type="html")
        )

        self.assertEqual([item["item"] for item in items], ["2"])

    def test_non_heading_block_yields_low_heading_confidence(self) -> None:
        indexes = _heading_block_indexes(HTML_WITH_TOC)
        page_number_index = indexes["1"]["toc"] + 1  # the "3" page-number cell
        client = FakeClient(
            payload=_items_payload(
                {"1": page_number_index, "2": indexes["2"]["body"]}
            )
        )
        extractor = Layer2Extractor(client=client)

        items = extractor.extract(
            FilingDocument(content=HTML_WITH_TOC, document_type="html")
        )

        item_1 = next(item for item in items if item["item"] == "1")
        self.assertEqual(item_1["confidence"]["heading"], 0.0)

    def test_llm_failure_raises_disambiguation_error(self) -> None:
        client = FakeClient(error=RuntimeError("connection reset"))
        extractor = Layer2Extractor(client=client)

        with self.assertRaises(LLMDisambiguationError):
            extractor.extract(
                FilingDocument(content=HTML_WITH_TOC, document_type="html")
            )

    def test_invalid_document_type_fails(self) -> None:
        extractor = Layer2Extractor(client=FakeClient(payload={}))
        with self.assertRaises(ValueError):
            extractor.extract(FilingDocument(content=b"", document_type="pdf"))


if __name__ == "__main__":
    unittest.main()
