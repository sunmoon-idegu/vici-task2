"""Layer 2: language-model re-extraction of Item boundaries.

Layer 1 finds Item boundaries with regular expressions applied block by
block. If its confidence is too low, Layer 2 sends the whole normalized
document to a language model and asks it to find the Item boundaries
itself, using full-document context Layer 1's local heuristics don't
have. The model never returns filing content — only the item code and
the index of the block where each Item's body heading begins. The
program slices `content` from the original normalized text using that
index, exactly as Layer 1 does, so the model can never rewrite,
summarize, or omit filing content.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Dict, List, Optional

from anthropic import Anthropic

from app.core.config import settings
from app.core.exceptions import LLMDisambiguationError
from app.evaluations.confidence_evaluator import (
    ITEM_HEADING_RE,
    VALID_ITEMS,
    HeadingCandidate,
    calculate_body_vs_toc_confidence,
    calculate_heading_confidence,
)
from app.services.extraction.extractors.layer1_extractor import (
    EXPECTED_TITLES,
    Candidate,
    NormalizedDocument,
    evaluate_selected_items,
    normalize_html_document,
    normalize_text_document,
)

if TYPE_CHECKING:
    from app.models.filing_document import FilingDocument


ITEMS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "block_index": {"type": "integer"},
                },
                "required": ["item", "block_index"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You extract Item boundaries from a SEC Form 10-K filing. You are "
    "given the filing as a numbered list of normalized text blocks, in "
    "document order. Some blocks are real Item body headings, such as "
    "'ITEM 1A. RISK FACTORS'; others are table-of-contents rows, running "
    "page headers, or cross-references that only mention an Item in "
    "passing. For every standard Form 10-K Item that actually has a body "
    "section in this document, return the block_index of the block where "
    "that Item's real body heading begins. The 'item' field must be only "
    "the bare item code, such as \"1\", \"1A\", \"7A\", \"9C\", or \"16\" "
    "-- never the word 'Item', the title, or any other text. Do not "
    "include Items that do not appear in the document. Do not invent, "
    "summarize, or return any filing text -- only item codes and block "
    "indices."
)

# Tolerates the model returning "ITEM 1A. RISK FACTORS" or "Item 1A" or
# just "1A" -- always reduces to the bare code before checking VALID_ITEMS.
_ITEM_CODE_RE = re.compile(
    r"^\s*(?:ITEM\s+)?(?P<code>1A|1B|1C|7A|8A|8B|9A|9B|9C|1[0-6]|[1-9])\b",
    re.IGNORECASE,
)


def _normalize_item_code(raw: str) -> Optional[str]:
    match = _ITEM_CODE_RE.match(raw)
    if not match:
        return None
    code = match.group("code").upper()
    return code if code in VALID_ITEMS else None

# USD per 1M tokens. Keyed by model id; used only to print an estimated
# cost after each call, so an unrecognized model id falls back to the
# Haiku 4.5 rate rather than raising.
MODEL_PRICING_PER_MTOK = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}


def _normalize(document: "FilingDocument") -> NormalizedDocument:
    if document.document_type == "html":
        return normalize_html_document(document.content)
    if document.document_type == "txt":
        return normalize_text_document(document.content)
    raise ValueError("document_type must be 'html' or 'txt'")


def _build_prompt(normalized: NormalizedDocument) -> str:
    return "\n".join(
        f"[{index}] {block.text}"
        for index, block in enumerate(normalized.blocks)
    )


def _build_candidate(
    normalized: NormalizedDocument,
    item: str,
    block_index: int,
) -> Optional[Candidate]:
    if not 0 <= block_index < len(normalized.blocks):
        return None
    block = normalized.blocks[block_index]
    match = ITEM_HEADING_RE.match(block.text)
    title = match.group("title").strip() if match else EXPECTED_TITLES.get(item, "")
    return Candidate(item=item, title=title, block=block, heading=0.0, body_vs_toc=0.0)


class Layer2Extractor:
    """Re-extract Item boundaries with a language model over the whole filing."""

    def __init__(
        self,
        client: Optional[Anthropic] = None,
        model: Optional[str] = None,
    ) -> None:
        self.client = client or Anthropic()
        self.model = model or settings.llm_model

    def extract(self, document: "FilingDocument") -> List[dict]:
        normalized = _normalize(document)
        selections = self._extract_boundaries(normalized)

        candidates = [
            candidate
            for item, block_index in selections.items()
            for candidate in [_build_candidate(normalized, item, block_index)]
            if candidate is not None
        ]
        candidates.sort(key=lambda candidate: candidate.block.start)
        self._score_candidates(normalized, candidates)

        # No regex candidate list is passed here: the model already
        # reviewed the whole document, so there is nothing else to check
        # for "skipped" headings the way Layer 1 does locally.
        return evaluate_selected_items(normalized, [], candidates)

    def _score_candidates(
        self,
        normalized: NormalizedDocument,
        candidates: List[Candidate],
    ) -> None:
        for index, candidate in enumerate(candidates):
            next_start = (
                candidates[index + 1].block.start
                if index + 1 < len(candidates)
                else len(normalized.text)
            )
            heading_candidate = HeadingCandidate(
                text=candidate.block.text,
                expected_item=candidate.item,
                expected_title=EXPECTED_TITLES.get(candidate.item, ""),
                tag=candidate.block.tag,
                is_own_dom_block=candidate.block.is_own_dom_block,
                has_blank_before=candidate.block.has_blank_before,
                has_blank_after=candidate.block.has_blank_after,
                is_bold=candidate.block.is_bold,
                is_only_html_link=candidate.block.is_only_html_link,
            )
            candidate.heading = calculate_heading_confidence(heading_candidate)
            candidate.body_vs_toc = calculate_body_vs_toc_confidence(
                heading_candidate,
                characters_to_next_heading=max(
                    0, next_start - candidate.block.end
                ),
                nearby_heading_count=0,
                has_later_duplicate=False,
            )

    def _extract_boundaries(
        self,
        normalized: NormalizedDocument,
    ) -> Dict[str, int]:
        prompt = _build_prompt(normalized)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": ITEMS_SCHEMA,
                    }
                },
                messages=[{"role": "user", "content": prompt}],
            )
            text = next(
                block.text for block in response.content if block.type == "text"
            )
            payload = json.loads(text)
        except Exception as exc:  # noqa: BLE001 - normalize every failure mode
            raise LLMDisambiguationError(str(exc)) from exc

        self._print_cost(response.usage)

        selections: Dict[str, int] = {}
        for entry in payload.get("items", []):
            if not isinstance(entry, dict):
                continue
            item = _normalize_item_code(str(entry.get("item", "")))
            block_index = entry.get("block_index")
            if item is not None and isinstance(block_index, int):
                selections[item] = block_index
        return selections

    def _print_cost(self, usage) -> None:
        pricing = MODEL_PRICING_PER_MTOK.get(
            self.model, MODEL_PRICING_PER_MTOK["claude-haiku-4-5"]
        )
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cost = (
            input_tokens / 1_000_000 * pricing["input"]
            + output_tokens / 1_000_000 * pricing["output"]
        )
        print(
            f"[layer2] model={self.model} "
            f"input_tokens={input_tokens} output_tokens={output_tokens} "
            f"cost=${cost:.6f}"
        )
