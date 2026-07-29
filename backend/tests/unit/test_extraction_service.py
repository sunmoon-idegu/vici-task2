"""Tests for the extraction workflow over prepared input."""

import unittest

from app.core.exceptions import FilingExtractionError, LLMDisambiguationError
from app.models.filing_document import FilingDocument
from app.services.extraction.extraction_service import ExtractionService


class FakeExtractor:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.received = None

    def extract(self, document):
        self.received = document
        if self.error:
            raise self.error
        return self.result


class ExtractionServiceTests(unittest.TestCase):
    def test_service_receives_prepared_document(self) -> None:
        item = {
            "confidence": {
                "score": 0.9,
            }
        }
        extractor = FakeExtractor(result=[item])
        service = ExtractionService(
            layer1=extractor,
            layer2=FakeExtractor(),
        )
        document = FilingDocument(b"prepared", "html")

        result = service.extract(document)

        self.assertIs(extractor.received, document)
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.layer, "layer1")

    def test_extraction_value_error_becomes_application_error(self) -> None:
        service = ExtractionService(
            layer1=FakeExtractor(error=ValueError("unsupported document")),
            layer2=FakeExtractor(),
        )

        with self.assertRaises(FilingExtractionError):
            service.extract(FilingDocument(b"", "pdf"))

    def test_low_confidence_falls_through_to_layer2(self) -> None:
        layer1_item = {"confidence": {"score": 0.881}}
        layer2_item = {"confidence": {"score": 0.95}}
        layer1 = FakeExtractor(result=[layer1_item])
        layer2 = FakeExtractor(result=[layer2_item])
        service = ExtractionService(layer1=layer1, layer2=layer2)
        document = FilingDocument(b"prepared", "html")

        result = service.extract(document)

        self.assertIs(layer2.received, document)
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.layer, "layer2")

    def test_layer2_failure_falls_back_to_layer1_result(self) -> None:
        layer1_item = {"confidence": {"score": 0.881}}
        layer1 = FakeExtractor(result=[layer1_item])
        layer2 = FakeExtractor(error=LLMDisambiguationError("boom"))
        service = ExtractionService(layer1=layer1, layer2=layer2)
        document = FilingDocument(b"prepared", "html")

        result = service.extract(document)

        self.assertEqual(result.confidence, 0.881)
        self.assertEqual(result.layer, "layer1")
