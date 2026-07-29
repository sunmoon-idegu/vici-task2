"""Layered extraction workflow over a prepared filing document."""

from app.core.config import settings
from app.core.exceptions import FilingExtractionError, LLMDisambiguationError
from app.evaluations.confidence_evaluator import calculate_filing_confidence
from app.models.extraction_result import ExtractionResult
from app.models.filing_document import FilingDocument
from app.services.extraction.extractors.layer1_extractor import (
    Layer1Extractor,
)
from app.services.extraction.extractors.layer2_extractor import (
    Layer2Extractor,
)


class ExtractionService:
    """Run extraction layers, falling through while confidence is low."""

    def __init__(
        self,
        layer1: Layer1Extractor = None,
        layer2: Layer2Extractor = None,
    ) -> None:
        self.layer1 = layer1 or Layer1Extractor()
        self.layer2 = layer2 or Layer2Extractor()

    def extract(self, document: FilingDocument) -> ExtractionResult:
        try:
            items = self.layer1.extract(document)
        except ValueError as exc:
            raise FilingExtractionError(str(exc)) from exc
        confidence = calculate_filing_confidence(
            item["confidence"]["score"] for item in items
        )
        layer = "layer1"

        if confidence < settings.confidence_threshold:
            try:
                layer2_items = self.layer2.extract(document)
            except (ValueError, LLMDisambiguationError):
                layer2_items = None
            if layer2_items is not None:
                items = layer2_items
                confidence = calculate_filing_confidence(
                    item["confidence"]["score"] for item in items
                )
                layer = "layer2"

        return ExtractionResult(
            items=items,
            confidence=confidence,
            layer=layer,
        )
