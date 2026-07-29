"""Prepared filing input consumed by extraction services."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FilingDocument:
    content: bytes
    document_type: str
