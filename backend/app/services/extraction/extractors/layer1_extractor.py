"""Layer 1 deterministic Item extraction for SEC Form 10-K documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape, unescape
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Sequence, Tuple
from lxml import etree, html

from app.evaluations.confidence_evaluator import (
    ITEM_HEADING_RE,
    HeadingCandidate,
    calculate_body_vs_toc_confidence,
    calculate_content_present,
    calculate_filing_confidence,
    calculate_heading_confidence,
    calculate_item_confidence,
    calculate_no_skipped_heading,
    calculate_section_confidence,
    source_slice_is_valid,
)

if TYPE_CHECKING:
    from app.models.filing_document import FilingDocument


SUPPORTED_FORM_TYPES = frozenset({"10-K", "10-K405"})
BLOCK_TAGS = frozenset(
    {
        "address",
        "blockquote",
        "caption",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "pre",
        "td",
        "th",
    }
)
EXPECTED_TITLES = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": (
        "Market for Registrant's Common Equity, Related Stockholder "
        "Matters and Issuer Purchases of Equity Securities"
    ),
    "6": "Reserved",
    "7": (
        "Management's Discussion and Analysis of Financial Condition "
        "and Results of Operations"
    ),
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": (
        "Changes in and Disagreements With Accountants on Accounting "
        "and Financial Disclosure"
    ),
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": (
        "Disclosure Regarding Foreign Jurisdictions that Prevent "
        "Inspections"
    ),
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "12": (
        "Security Ownership of Certain Beneficial Owners and Management "
        "and Related Stockholder Matters"
    ),
    "13": (
        "Certain Relationships and Related Transactions, and Director "
        "Independence"
    ),
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibits and Financial Statement Schedules",
    "16": "Form 10-K Summary",
}
DOCUMENT_RE = re.compile(
    r"<DOCUMENT>(?P<document>.*?)</DOCUMENT>",
    re.IGNORECASE | re.DOTALL,
)
TYPE_RE = re.compile(r"<TYPE>\s*(?P<type>[^\r\n<]+)", re.IGNORECASE)
TEXT_RE = re.compile(r"<TEXT>(?P<text>.*)</TEXT>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
SIGNATURE_RE = re.compile(r"^\s*signatures?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class TextBlock:
    text: str
    start: int
    end: int
    tag: Optional[str] = None
    is_own_dom_block: bool = False
    has_blank_before: bool = False
    has_blank_after: bool = False
    is_bold: bool = False
    is_only_html_link: bool = False


@dataclass(frozen=True)
class RichBlock:
    html: str
    start: int
    end: int


@dataclass
class Candidate:
    item: str
    title: str
    block: TextBlock
    heading: float
    body_vs_toc: float = 0.0

    @property
    def selection_score(self) -> float:
        return round(0.4 * self.heading + 0.6 * self.body_vs_toc, 3)


@dataclass(frozen=True)
class NormalizedDocument:
    text: str
    blocks: Sequence[TextBlock]
    rich_blocks: Sequence[RichBlock]


def _clean_text(text: str) -> str:
    text = unescape(text).replace("\xa0", " ")
    return " ".join(text.split())


def _build_blocks(
    raw_blocks: Iterable[
        Tuple[str, Optional[str], bool, bool, bool, bool, bool]
    ],
) -> Tuple[str, List[TextBlock]]:
    pieces: List[str] = []
    blocks: List[TextBlock] = []
    position = 0

    for (
        block_text,
        tag,
        own_block,
        blank_before,
        blank_after,
        is_bold,
        only_link,
    ) in raw_blocks:
        cleaned = _clean_text(block_text)
        if not cleaned:
            continue
        if pieces:
            pieces.append("\n\n")
            position += 2
        start = position
        pieces.append(cleaned)
        position += len(cleaned)
        blocks.append(
            TextBlock(
                text=cleaned,
                start=start,
                end=position,
                tag=tag,
                is_own_dom_block=own_block,
                has_blank_before=blank_before,
                has_blank_after=blank_after,
                is_bold=is_bold,
                is_only_html_link=only_link,
            )
        )

    return "".join(pieces), blocks


def _local_name(element: etree._Element) -> str:
    if not isinstance(element.tag, str):
        return ""
    return element.tag.rsplit("}", 1)[-1].lower()


def _has_block_descendant(element: etree._Element) -> bool:
    return any(
        descendant is not element
        and _local_name(descendant) in BLOCK_TAGS
        and _clean_text(" ".join(descendant.itertext()))
        for descendant in element.iterdescendants()
    )


def _element_is_bold(element: etree._Element) -> bool:
    if _local_name(element) in {"b", "strong"}:
        return True
    style = (element.get("style") or "").lower().replace(" ", "")
    if "font-weight:bold" in style:
        return True
    match = re.search(r"font-weight:(\d+)", style)
    if match and int(match.group(1)) >= 600:
        return True

    text = _clean_text(" ".join(element.itertext()))
    if not text:
        return False
    bold_text = " ".join(
        " ".join(node.itertext())
        for node in element.iter()
        if node is not element and _local_name(node) in {"b", "strong"}
    )
    return len(_clean_text(bold_text)) / len(text) >= 0.8


def _element_is_only_link(element: etree._Element) -> bool:
    text = _clean_text(" ".join(element.itertext()))
    links = element.xpath(".//a | self::a")
    if not text or not links:
        return False
    link_text = _clean_text(" ".join(" ".join(link.itertext()) for link in links))
    return link_text == text


def _nearest_table(element: etree._Element) -> Optional[etree._Element]:
    for ancestor in element.iterancestors():
        if _local_name(ancestor) == "table":
            return ancestor
    return None


def _table_to_html(table: etree._Element) -> str:
    rows = []
    for row in table.xpath(".//*[local-name()='tr']"):
        cells = []
        for cell in row.xpath(
            "./*[local-name()='th' or local-name()='td']"
        ):
            tag = _local_name(cell)
            attributes = []
            for name in ("colspan", "rowspan"):
                value = cell.get(name)
                if value and value.isdigit():
                    attributes.append(f' {name}="{value}"')
            text = escape(_clean_text(" ".join(cell.itertext())))
            cells.append(
                f"<{tag}{''.join(attributes)}>{text}</{tag}>"
            )
        if cells:
            rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table><tbody>{''.join(rows)}</tbody></table>"


def _element_to_html(element: etree._Element, text: str) -> str:
    escaped = escape(text)
    tag = _local_name(element)
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return f"<{tag}>{escaped}</{tag}>"
    if tag == "li":
        return f"<ul><li>{escaped}</li></ul>"
    if tag == "pre":
        return f"<pre>{escaped}</pre>"
    return f"<p>{escaped}</p>"


def normalize_html_document(data: bytes) -> NormalizedDocument:
    root = html.fromstring(data)
    for unwanted in root.xpath("//script | //style | //noscript"):
        unwanted.drop_tree()

    raw_blocks = []
    elements = []
    for element in root.iter():
        tag = _local_name(element)
        if tag not in BLOCK_TAGS or _has_block_descendant(element):
            continue
        text = " ".join(element.itertext())
        if not _clean_text(text):
            continue
        raw_blocks.append(
            (
                text,
                tag,
                True,
                False,
                False,
                _element_is_bold(element),
                _element_is_only_link(element),
            )
        )
        elements.append(element)

    normalized_text, blocks = _build_blocks(raw_blocks)
    rich_blocks = []
    handled_tables = set()
    for element, block in zip(elements, blocks):
        table = _nearest_table(element)
        if table is None and _local_name(element) == "table":
            table = element
        if table is not None:
            table_id = id(table)
            if table_id in handled_tables:
                continue
            handled_tables.add(table_id)
            table_indexes = [
                index
                for index, other_element in enumerate(elements)
                if other_element is table or table in other_element.iterancestors()
            ]
            if not table_indexes:
                continue
            first = blocks[min(table_indexes)]
            last = blocks[max(table_indexes)]
            rich_blocks.append(
                RichBlock(
                    html=_table_to_html(table),
                    start=first.start,
                    end=last.end,
                )
            )
            continue
        rich_blocks.append(
            RichBlock(
                html=_element_to_html(element, block.text),
                start=block.start,
                end=block.end,
            )
        )
    rich_blocks.sort(key=lambda rich_block: rich_block.start)
    return NormalizedDocument(
        text=normalized_text,
        blocks=blocks,
        rich_blocks=rich_blocks,
    )


def select_10k_document(submission: str) -> Tuple[str, str]:
    documents = list(DOCUMENT_RE.finditer(submission))
    if not documents:
        header_type = re.search(
            r"CONFORMED SUBMISSION TYPE:\s*([^\r\n]+)",
            submission,
            re.IGNORECASE,
        )
        form_type = header_type.group(1).strip() if header_type else "10-K"
        if form_type not in SUPPORTED_FORM_TYPES:
            raise ValueError(f"Unsupported filing type: {form_type}")
        return submission, form_type

    for document_match in documents:
        document = document_match.group("document")
        type_match = TYPE_RE.search(document)
        if not type_match:
            continue
        form_type = type_match.group("type").strip().upper()
        if form_type not in SUPPORTED_FORM_TYPES:
            continue
        text_match = TEXT_RE.search(document)
        return (
            text_match.group("text") if text_match else document,
            form_type,
        )
    raise ValueError("Complete submission does not contain a supported 10-K")


def normalize_text_document(data: bytes) -> NormalizedDocument:
    submission = data.decode("utf-8", errors="replace")
    if "\ufffd" in submission:
        submission = data.decode("latin-1", errors="replace")
    document, _ = select_10k_document(submission)

    document = re.sub(
        r"<(?:PAGE|TABLE|S|C|CAPTION|FN|F|I|B)(?:\s[^>]*)?>",
        "\n",
        document,
        flags=re.IGNORECASE,
    )
    document = TAG_RE.sub(" ", document)
    lines = document.splitlines()
    raw_blocks = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        blank_before = index == 0 or not lines[index - 1].strip()
        blank_after = index == len(lines) - 1 or not lines[index + 1].strip()
        raw_blocks.append(
            (
                line,
                None,
                False,
                blank_before,
                blank_after,
                False,
                False,
            )
        )
    normalized_text, blocks = _build_blocks(raw_blocks)
    return NormalizedDocument(
        text=normalized_text,
        blocks=blocks,
        rich_blocks=[
            RichBlock(
                html=f"<p>{escape(block.text)}</p>",
                start=block.start,
                end=block.end,
            )
            for block in blocks
        ],
    )


def _heading_candidate(block: TextBlock) -> Optional[Candidate]:
    match = ITEM_HEADING_RE.match(block.text)
    if match is None:
        return None
    item = match.group("item").upper()
    title = match.group("title").strip()
    evaluation_candidate = HeadingCandidate(
        text=block.text,
        expected_item=item,
        expected_title=EXPECTED_TITLES.get(item, ""),
        tag=block.tag,
        is_own_dom_block=block.is_own_dom_block,
        has_blank_before=block.has_blank_before,
        has_blank_after=block.has_blank_after,
        is_bold=block.is_bold,
        is_only_html_link=block.is_only_html_link,
    )
    return Candidate(
        item=item,
        title=title,
        block=block,
        heading=calculate_heading_confidence(evaluation_candidate),
    )


def find_candidates(document: NormalizedDocument) -> List[Candidate]:
    candidates = [
        candidate
        for block in document.blocks
        for candidate in [_heading_candidate(block)]
        if candidate is not None
    ]

    for index, candidate in enumerate(candidates):
        next_start = (
            candidates[index + 1].block.start
            if index + 1 < len(candidates)
            else len(document.text)
        )
        nearby_count = sum(
            1
            for other in candidates[index + 1 :]
            if other.block.start - candidate.block.end <= 1_000
        )
        later_duplicate = any(
            other.item == candidate.item and other.heading >= 0.80
            for other in candidates[index + 1 :]
        )
        evaluation_candidate = HeadingCandidate(
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
        candidate.body_vs_toc = calculate_body_vs_toc_confidence(
            evaluation_candidate,
            characters_to_next_heading=max(0, next_start - candidate.block.end),
            nearby_heading_count=nearby_count,
            has_later_duplicate=later_duplicate,
        )
    return candidates


def select_candidates(candidates: Sequence[Candidate]) -> List[Candidate]:
    by_item: Dict[str, List[Candidate]] = {}
    for candidate in candidates:
        by_item.setdefault(candidate.item, []).append(candidate)

    selected = [
        max(
            item_candidates,
            key=lambda candidate: (
                candidate.selection_score,
                candidate.block.start,
            ),
        )
        for item_candidates in by_item.values()
    ]
    return sorted(selected, key=lambda candidate: candidate.block.start)


def _find_terminal_position(
    document: NormalizedDocument,
    after: int,
) -> Tuple[int, float]:
    for block in document.blocks:
        if block.start > after and SIGNATURE_RE.match(block.text):
            return block.start, 1.0
    return len(document.text), 0.5


def evaluate_selected_items(
    document: NormalizedDocument,
    all_candidates: Sequence[Candidate],
    selected: Sequence[Candidate],
) -> List[dict]:
    selected_ids = {id(candidate) for candidate in selected}
    items = []

    for index, candidate in enumerate(selected):
        if index + 1 < len(selected):
            next_candidate = selected[index + 1]
            end = next_candidate.block.start
            end_boundary = next_candidate.heading
        else:
            end, end_boundary = _find_terminal_position(
                document,
                candidate.block.end,
            )

        start = candidate.block.start
        content = document.text[start:end]
        content_html = "".join(
            rich_block.html
            for rich_block in document.rich_blocks
            if start <= rich_block.start < end
        )
        body_content = document.text[candidate.block.end:end].strip()
        skipped_confidences = [
            other.heading
            for other in all_candidates
            if id(other) not in selected_ids
            and candidate.block.end < other.block.start < end
        ]
        no_skipped_heading = calculate_no_skipped_heading(
            skipped_confidences
        )
        content_present = calculate_content_present(
            body_content,
            heading_title=candidate.title,
        )
        slice_valid = source_slice_is_valid(
            source=document.text,
            content=content,
            start=start,
            end=end,
        )
        section = calculate_section_confidence(
            end_boundary=end_boundary,
            no_skipped_heading=no_skipped_heading,
            content_present=content_present,
            source_slice_valid=slice_valid,
        )
        item_score = calculate_item_confidence(
            heading=candidate.heading,
            body_vs_toc=candidate.body_vs_toc,
            section=section,
        )
        items.append(
            {
                "item": candidate.item,
                "title": candidate.title,
                "content": content,
                "content_html": content_html,
                "start": start,
                "end": end,
                "confidence": {
                    "score": item_score,
                    "heading": candidate.heading,
                    "body_vs_toc": candidate.body_vs_toc,
                    "section": section,
                },
            }
        )
    return items


def extract_items_from_bytes(
    data: bytes,
    *,
    document_type: str,
) -> List[dict]:
    if document_type == "html":
        document = normalize_html_document(data)
    elif document_type == "txt":
        document = normalize_text_document(data)
    else:
        raise ValueError("document_type must be 'html' or 'txt'")

    candidates = find_candidates(document)
    selected = select_candidates(candidates)
    return evaluate_selected_items(document, candidates, selected)


def filing_confidence(items: Sequence[dict]) -> float:
    return calculate_filing_confidence(
        item["confidence"]["score"] for item in items
    )


class Layer1Extractor:
    """Extract Items from a prepared filing document without external I/O."""

    def extract(self, document: "FilingDocument") -> List[dict]:
        return extract_items_from_bytes(
            document.content,
            document_type=document.document_type,
        )
