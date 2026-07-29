"""Layered extraction workflow over a prepared filing document."""

from app.evaluations.confidence_evaluator import calculate_filing_confidence
from app.core.exceptions import FilingExtractionError
from app.models.extraction_result import ExtractionResult
from app.models.filing_document import FilingDocument
from app.services.extraction.extractors.layer1_extractor import (
    Layer1Extractor,
)


class ExtractionService:
    """Run extraction layers; currently only deterministic Layer 1."""

    def __init__(self, layer1: Layer1Extractor = None) -> None:
        self.layer1 = layer1 or Layer1Extractor()

    def extract(self, document: FilingDocument) -> ExtractionResult:
        try:
            items = self.layer1.extract(document)
        except ValueError as exc:
            raise FilingExtractionError(str(exc)) from exc
        confidence = calculate_filing_confidence(
            item["confidence"]["score"] for item in items
        )
        return ExtractionResult(
            items=items,
            confidence=confidence,
            layer="layer1",
        )
