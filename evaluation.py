"""Deterministic confidence scoring for extracted Form 10-K Items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional


VALID_ITEMS = frozenset(
    {
        "1",
        "1A",
        "1B",
        "1C",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "7A",
        "8",
        "9",
        "9A",
        "9B",
        "9C",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
    }
)

ITEM_HEADING_RE = re.compile(
    r"^\s*item\s+"
    r"(?P<item>1A|1B|1C|7A|9A|9B|9C|1[0-6]|[1-9])"
    r"(?![A-Za-z0-9(])[.\-:–—\s]*(?P<title>.*)$",
    re.IGNORECASE,
)
DOT_LEADER_RE = re.compile(r"\.{2,}\s*\d+\s*$")
SPACED_PAGE_NUMBER_RE = re.compile(r"\S\s{2,}\d+\s*$")
SHORT_RESPONSES = frozenset({"none", "not applicable", "n a"})


@dataclass(frozen=True)
class HeadingCandidate:
    """Source metadata needed to evaluate a possible Item heading."""

    text: str
    expected_item: Optional[str] = None
    expected_title: str = ""
    tag: Optional[str] = None
    is_own_dom_block: bool = False
    has_blank_before: bool = False
    has_blank_after: bool = False
    is_bold: bool = False
    is_only_html_link: bool = False


@dataclass(frozen=True)
class ConfidenceWeights:
    heading: float = 1 / 3
    body_vs_toc: float = 1 / 3
    section: float = 1 / 3

    def __post_init__(self) -> None:
        values = (self.heading, self.body_vs_toc, self.section)
        if any(value < 0 for value in values):
            raise ValueError("Confidence weights cannot be negative")
        if not _approximately_equal(sum(values), 1.0):
            raise ValueError("Confidence weights must sum to 1")


def _approximately_equal(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-9


def _require_unit_interval(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


def normalize_title(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def calculate_title_similarity(
    detected_title: str,
    expected_title: str,
) -> float:
    detected = normalize_title(detected_title)
    expected = normalize_title(expected_title)
    if not detected or not expected:
        return 0.0
    return round(SequenceMatcher(None, detected, expected).ratio(), 3)


def is_mostly_uppercase(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    uppercase = sum(character.isupper() for character in letters)
    return uppercase / len(letters) >= 0.8


def calculate_heading_format(candidate: HeadingCandidate) -> float:
    normalized_text = " ".join(candidate.text.split())
    is_short = len(normalized_text) <= 120
    is_isolated = (
        candidate.is_own_dom_block
        or candidate.has_blank_before
        or candidate.has_blank_after
    )
    is_heading_tag = (candidate.tag or "").lower() in {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }
    is_emphasized = (
        is_heading_tag
        or candidate.is_bold
        or is_mostly_uppercase(candidate.text)
    )
    return round(
        0.4 * float(is_short)
        + 0.3 * float(is_isolated)
        + 0.3 * float(is_emphasized),
        3,
    )


def calculate_heading_confidence(candidate: HeadingCandidate) -> float:
    match = ITEM_HEADING_RE.match(candidate.text)
    if match is None:
        return 0.0

    detected_item = match.group("item").upper()
    expected_item = (
        candidate.expected_item.upper() if candidate.expected_item else None
    )
    item_identifier = float(
        detected_item in VALID_ITEMS
        and (expected_item is None or detected_item == expected_item)
    )
    if item_identifier == 0.0:
        return 0.0

    heading_format = calculate_heading_format(candidate)
    title_similarity = calculate_title_similarity(
        match.group("title"),
        candidate.expected_title,
    )
    return round(
        0.70 * item_identifier
        + 0.20 * heading_format
        + 0.10 * title_similarity,
        3,
    )


def calculate_content_after(characters_to_next_heading: int) -> float:
    if characters_to_next_heading < 0:
        raise ValueError("characters_to_next_heading cannot be negative")
    if characters_to_next_heading >= 500:
        return 1.0
    if characters_to_next_heading >= 100:
        return 0.5
    return 0.0


def has_toc_format(candidate: HeadingCandidate) -> bool:
    text = candidate.text.strip()
    return (
        candidate.is_only_html_link
        or DOT_LEADER_RE.search(text) is not None
        or SPACED_PAGE_NUMBER_RE.search(text) is not None
    )


def calculate_low_heading_density(nearby_heading_count: int) -> float:
    if nearby_heading_count < 0:
        raise ValueError("nearby_heading_count cannot be negative")
    if nearby_heading_count <= 2:
        return 1.0
    if nearby_heading_count <= 4:
        return 0.5
    return 0.0


def calculate_body_vs_toc_confidence(
    candidate: HeadingCandidate,
    *,
    characters_to_next_heading: int,
    nearby_heading_count: int,
    has_later_duplicate: bool,
) -> float:
    content_after = calculate_content_after(characters_to_next_heading)
    no_toc_format = float(not has_toc_format(candidate))
    low_heading_density = calculate_low_heading_density(nearby_heading_count)
    no_later_duplicate = float(not has_later_duplicate)
    return round(
        0.35 * content_after
        + 0.30 * no_toc_format
        + 0.20 * low_heading_density
        + 0.15 * no_later_duplicate,
        3,
    )


def calculate_no_skipped_heading(
    unselected_heading_confidences: Iterable[float],
    *,
    uncertain_threshold: float = 0.70,
    strong_threshold: float = 0.90,
) -> float:
    if not 0.0 <= uncertain_threshold <= strong_threshold <= 1.0:
        raise ValueError("Skipped-heading thresholds are invalid")

    confidences = list(unselected_heading_confidences)
    for confidence in confidences:
        _require_unit_interval("unselected heading confidence", confidence)

    strongest = max(confidences, default=0.0)
    if strongest >= strong_threshold:
        return 0.0
    if strongest >= uncertain_threshold:
        return 0.5
    return 1.0


def calculate_content_present(
    body_text: str,
    *,
    heading_title: str = "",
) -> float:
    normalized = normalize_title(body_text)
    normalized_title = normalize_title(heading_title)
    if normalized_title == "reserved":
        return 1.0
    if not normalized:
        return 0.0
    if normalized in SHORT_RESPONSES:
        return 1.0
    if "incorporated by reference" in normalized:
        return 1.0
    if len(body_text.strip()) >= 100:
        return 1.0
    return 0.5


def source_slice_is_valid(
    *,
    source: str,
    content: str,
    start: int,
    end: int,
    overlaps_another_item: bool = False,
) -> bool:
    return (
        0 <= start < end <= len(source)
        and not overlaps_another_item
        and content == source[start:end]
    )


def calculate_section_confidence(
    *,
    end_boundary: float,
    no_skipped_heading: float,
    content_present: float,
    source_slice_valid: bool = True,
) -> float:
    _require_unit_interval("end_boundary", end_boundary)
    _require_unit_interval("no_skipped_heading", no_skipped_heading)
    _require_unit_interval("content_present", content_present)
    if not source_slice_valid:
        return 0.0
    return round(
        0.40 * end_boundary
        + 0.40 * no_skipped_heading
        + 0.20 * content_present,
        3,
    )


def calculate_item_confidence(
    *,
    heading: float,
    body_vs_toc: float,
    section: float,
    weights: ConfidenceWeights = ConfidenceWeights(),
) -> float:
    _require_unit_interval("heading", heading)
    _require_unit_interval("body_vs_toc", body_vs_toc)
    _require_unit_interval("section", section)
    return round(
        weights.heading * heading
        + weights.body_vs_toc * body_vs_toc
        + weights.section * section,
        3,
    )


def calculate_filing_confidence(
    item_confidences: Iterable[float],
) -> float:
    confidences = list(item_confidences)
    if not confidences:
        return 0.0
    for confidence in confidences:
        _require_unit_interval("item confidence", confidence)
    return round(sum(confidences) / len(confidences), 3)
