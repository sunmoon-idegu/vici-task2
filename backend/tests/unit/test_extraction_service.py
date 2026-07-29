"""Tests for the extraction workflow over prepared input."""

import unittest

from app.core.exceptions import FilingExtractionError
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
        service = ExtractionService(layer1=extractor)
        document = FilingDocument(b"prepared", "html")

        result = service.extract(document)

        self.assertIs(extractor.received, document)
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.layer, "layer1")

    def test_extraction_value_error_becomes_application_error(self) -> None:
        service = ExtractionService(
            layer1=FakeExtractor(error=ValueError("unsupported document"))
        )

        with self.assertRaises(FilingExtractionError):
            service.extract(FilingDocument(b"", "pdf"))
