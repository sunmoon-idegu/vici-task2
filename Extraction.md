# Extraction

This document explains in detail how the deterministic Layer 1 extractor processes a SEC filing from input to output. It covers downloading, HTML and TXT normalization, main-document selection, heading detection, candidate selection, content boundaries, presentation HTML, confidence integration, output format, tests, and current limitations.

## Layer 1

Layer 1 is a deterministic extractor implemented in `backend/app/services/extraction/extractors/layer1_extractor.py`. It uses regular expressions, `lxml`, document structure, and the confidence functions from `backend/app/evaluations/confidence_evaluator.py`. It does not use a language model.

## Input

The backend API accepts one SEC document URL:

```json
{
  "url": "https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/ko-20251231.htm"
}
```

Supported inputs currently include:

- A direct HTML 10-K document.
- An SEC complete-submission TXT file containing a `10-K`, `10-K405`,
  `10KSB`, or `10-KSB` document.

Internally, the repository downloads and prepares a `FilingDocument`. Layer 1 consumes that prepared input without performing external I/O:

```python
items = Layer1Extractor().extract(filing_document)
```

URL allow-listing and stronger filing-type validation will be added separately. The current HTML path assumes the supplied document is a 10-K. The TXT path explicitly selects a supported 10-K document from the submission.

## Processing Steps

### 1. Download

`extract_items(url)` downloads the document with Python's standard HTTP library. The request includes a descriptive User-Agent and SEC-compatible request headers.

The document is treated as TXT when:

- The URL ends in `.txt`, or
- The HTTP content type is `text/plain`.

All other supported documents use the HTML path.

### 2. Select the Main Document

This step applies to complete-submission TXT files.

One submission may contain several `<DOCUMENT>` sections:

```text
<DOCUMENT>
<TYPE>10-K
...
</DOCUMENT>

<DOCUMENT>
<TYPE>EX-21
...
</DOCUMENT>
```

The extractor:

1. Finds every `<DOCUMENT>` section.
2. Reads its `<TYPE>`.
3. Selects the first supported annual-report document: `10-K`, `10-K405`,
   `10KSB`, or `10-KSB`.
4. Extracts the content inside `<TEXT>`.
5. Ignores exhibits and other document types.

If no supported document exists, extraction raises `ValueError`.

Direct HTML inputs do not require this step because their URL already points to the primary document.

### 3. Normalize the Document

HTML and TXT use separate normalization paths but produce the same internal representation:

```python
NormalizedDocument(
    text="normalized document text",
    blocks=[...],
    rich_blocks=[...],
)
```

#### HTML Normalization

The HTML path:

1. Parses the document with `lxml`.
2. Removes `script`, `style`, and `noscript` elements.
3. Walks visible leaf-level block elements in document order.
4. Collapses repeated whitespace.
5. Records metadata for each block:
   - Normalized character offsets.
   - HTML tag.
   - Bold styling.
   - Whether the block is isolated.
   - Whether it contains only a link.
6. Creates sanitized rich HTML blocks for presentation.

HTML tables are kept as tables. Rows, cells, `colspan`, and `rowspan` are preserved in `content_html`.

#### TXT Normalization

The TXT path:

1. Decodes UTF-8, with Latin-1 fallback.
2. Removes SEC SGML formatting tags.
3. Splits the document into non-empty lines.
4. Collapses repeated whitespace.
5. Records normalized character offsets and surrounding blank-line information.
6. Creates safe paragraph HTML for presentation.

### 4. Find Heading Candidates

Each normalized block is tested against an anchored Item-heading pattern:

```text
^\s*(PART\s+[IVX]+\s+)?ITEM\s+(1|1A|1B|...|16)
```

The Item identifier must appear at the beginning of the block, optionally after
a Part marker. Historical 10-KSB filings sometimes place both on one line.

Accepted:

```text
ITEM 1A. RISK FACTORS
ITEM 7A
PART II ITEM 5. MARKET FOR COMMON EQUITY
```

Rejected:

```text
See Item 1A for details
ITEM 14(a)2
```

Rejecting subitem headings such as `ITEM 14(a)2` prevents them from replacing the main Item 14 heading.

### 5. Evaluate Each Candidate

Each candidate receives two preliminary scores from `confidence_evaluator.py`:

- `heading`: how strongly the block resembles an Item heading.
- `body_vs_toc`: how likely it is to be a body heading instead of a table-of-contents entry.

The selection score is:

```text
selection_score =
    0.40 × heading
  + 0.60 × body_vs_toc
```

Body-versus-TOC receives more weight because a TOC entry can have a perfect Item number and title.

### 6. Select One Heading per Item

The extractor groups candidates by Item identifier:

```text
Item 1A
├── TOC candidate
└── body candidate
```

For each identifier, it selects the candidate with the highest selection score. Ties prefer the later candidate because the body commonly appears after the TOC.

Selected candidates are then sorted by normalized source position.

### 7. Extract Item Content

Each Item begins at its selected heading:

```text
start = selected heading position
```

It ends at the next selected heading:

```text
end = next selected heading position
```

The final Item ends at:

1. A standalone `SIGNATURES` marker, if found.
2. Otherwise, the end of the normalized main document.

The normalized content is always a direct slice:

```python
content = normalized_document_text[start:end]
```

The offsets refer to normalized text, not raw HTML bytes.

### 8. Produce Presentation HTML

Rich blocks whose normalized positions fall inside the Item boundaries are combined into:

```python
content_html
```

This representation is used only for presentation. It preserves HTML tables and safely escapes text. Confidence evaluation continues to use normalized `content`.

### 9. Calculate Confidence

For each selected Item, the extractor calculates:

- Heading confidence.
- Body-versus-TOC confidence.
- Section confidence.
- Overall Item confidence.

Section validation checks that:

- The end boundary is a strong next heading.
- No strong unselected heading was skipped.
- The section contains meaningful content.
- `content` exactly equals the normalized source slice.

Filing confidence is currently the average of all Item scores:

```text
filing_confidence =
    sum(item confidence) / number of Items
```

The detailed formulas are documented in `Evaluation.md`.

## Layer 2

Layer 2 is implemented in `backend/app/services/extraction/extractors/layer2_extractor.py`. `ExtractionService` runs it automatically whenever the Layer 1 filing confidence is below `settings.confidence_threshold` (0.90).

Layer 2 does not re-parse or rewrite the filing. It reuses Layer 1's normalization and heading-candidate detection (`normalize_html_document`/`normalize_text_document`, `find_candidates`) so it sees exactly the same candidates Layer 1 found. Most Items have only one candidate and are kept as-is. For Items with more than one candidate — typically a table-of-contents entry alongside the real body heading — Layer 2 asks a language model to pick which candidate index is the true body heading.

```text
candidates for Item 1A
  index 4  (TOC row, is_only_html_link=True)
  index 19 (bold body heading)
      ↓
  model returns candidate_index=19
```

The model only ever returns an index into the candidate list it was given; it never sees or returns filing text to slice from. The program then slices `content` from the chosen candidate's normalized offsets exactly as Layer 1 does, and confidence is recomputed with the same `evaluate_selected_items` / `calculate_item_confidence` functions from `confidence_evaluator.py`. This keeps Layer 2's output format and confidence semantics identical to Layer 1 — only candidate *selection* changes.

The model used is `claude-haiku-4-5` (`settings.llm_model`), called via `output_config.format` with a strict JSON schema (`{"selections": [{"item": ..., "candidate_index": ...}]}`) so the response is guaranteed valid JSON. If the model omits an Item or returns an index outside that Item's candidate list, Layer 2 falls back to Layer 1's heuristic (`selection_score = 0.40 × heading + 0.60 × body_vs_toc`, highest wins) for that Item only. If the API call itself fails, `ExtractionService` catches `LLMDisambiguationError` and returns the Layer 1 result unchanged — the service always returns its best available result.

`ANTHROPIC_API_KEY` is read from `backend/.env` (loaded via `python-dotenv`, not committed to git).

## Output

The result is a list of dictionaries in normalized document order:

```python
[
    {
        "item": "1A",
        "title": "RISK FACTORS",
        "content": "ITEM 1A. RISK FACTORS ...",
        "content_html": (
            "<p>ITEM 1A. RISK FACTORS</p>"
            "<p>Investing in our securities...</p>"
        ),
        "start": 124745,
        "end": 217125,
        "confidence": {
            "score": 1.0,
            "heading": 1.0,
            "body_vs_toc": 1.0,
            "section": 1.0,
        },
    }
]
```

`content` is the source of truth for offsets and evaluation. `content_html` is the presentation version.

## Current Test Results

| Filing | Input | Items found | Filing confidence |
|---|---|---:|---:|
| Coca-Cola 2025 10-K | HTML | 23 | 0.954 |
| Coca-Cola 1994 10-K405 | Complete-submission TXT | 14 | 0.952 |
| Network-1 Security Solutions 2006 10-KSB | TXT | 16 | 0.944 |

## Current Limitations

- Direct HTML inputs are not yet independently verified as 10-K filings.
- Complete-submission TXT selection supports `10-K`, historical `10-K405`,
  and historical `10KSB`/`10-KSB` filings. The 10-KSB title structure differs
  from modern Form 10-K, so title-similarity confidence may be lower.
- TXT tables remain flattened because old plain-text tables do not provide reliable structural markup.
- Candidate selection is heuristic and has only been tested against the current examples.
- Exact title expectations currently follow modern Form 10-K titles; historical wording only affects the small title-similarity component.
- Confidence scores are engineering scores and have not yet been calibrated against a labeled evaluation set.
