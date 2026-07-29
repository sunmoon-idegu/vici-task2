"""Pydantic schemas for extraction endpoints."""

from typing import List

from pydantic import BaseModel, HttpUrl


class ExtractionRequest(BaseModel):
    url: HttpUrl


class ConfidenceDetails(BaseModel):
    score: float
    heading: float
    body_vs_toc: float
    section: float


class ExtractedItem(BaseModel):
    item: str
    title: str
    content: str
    content_html: str
    start: int
    end: int
    confidence: ConfidenceDetails


class ExtractionResponse(BaseModel):
    confidence: float
    layer: str
    items: List[ExtractedItem]
