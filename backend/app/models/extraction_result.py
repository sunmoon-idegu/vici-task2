"""Internal extraction result returned by the extraction service."""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ExtractionResult:
    items: List[dict]
    confidence: float
    layer: str
