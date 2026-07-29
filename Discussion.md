# Design Discussion

This document records the current system scope, architectural decisions, layered extraction strategy, and the reasoning behind the implementation choices. It describes what the system is intended to do and how the extraction layers work together.

## Initial Scope

The first phase will not include a frontend or backend service. It will implement a simple Python function with the following contract:

- Input: a URL for an actual 10-K filing hosted in the SEC Archives.
- Output: the extracted Items, extraction confidence, the extraction layer used, and relevant warnings.
- The function will always return the best result it can produce, even when the final confidence is low. Uncertain results must be clearly identified.

The expected inputs include at least these two formats:

1. An HTML primary document, for example:
   `https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/ko-20251231.htm`
2. An SEC complete submission text file, for example:
   `https://www.sec.gov/Archives/edgar/data/21344/0000021344-95-000007.txt`

HTML and TXT inputs will be parsed separately. A complete submission text file may contain the primary filing document and multiple exhibits. The parser must first identify and isolate the actual 10-K document before extracting its Items.

The initial implementation is expected to support SEC form types that are substantively 10-K annual reports, including `10-K` and the historical `10-K405`. Support for other variants will be defined as relevant test cases are added.

## Layered Extraction Flow

The system uses a sequential fallback strategy. Each layer is an independent method capable of extracting all Item boundaries. A more expensive layer runs only if the current layer's confidence is below the acceptance threshold. Once a result meets the threshold, the system returns it immediately.

```text
Layer 1: Regular expressions + lxml
    ├─ confidence >= threshold → return the Layer 1 result
    └─ confidence <  threshold → continue to Layer 2

Layer 2: Small language model
    ├─ confidence >= threshold → return the Layer 2 result
    └─ confidence <  threshold → continue to Layer 3

Layer 3: Large language model
    └─ return the Layer 3 result regardless of confidence
```

### Layer 1: Regular Expressions and lxml

Layer 1 is implemented in `backend/app/services/extraction/extractors/layer1_extractor.py`. It uses separate HTML and TXT normalization paths and produces the same output schema for both.

```text
SEC URL
  → download
  → HTML or TXT normalization
  → heading candidates
  → candidate evaluation
  → body-heading selection
  → content slicing
  → Item and filing confidence
```

HTML documents are parsed with `lxml`. Visible leaf-level block elements are converted into normalized text blocks while preserving structural metadata such as tag name, bold styling, link-only content, and normalized character offsets.

Complete-submission TXT files are first split into `<DOCUMENT>` sections. The parser selects the document whose `<TYPE>` is `10-K` or `10-K405`, removes SGML formatting tags, and converts the remaining lines into normalized text blocks.

Only blocks beginning with a valid Item identifier become heading candidates. Each candidate receives heading and Body-versus-TOC scores from `backend/app/evaluations/confidence_evaluator.py`. When an Item occurs more than once, such as in both the TOC and body, Layer 1 selects the candidate with the strongest combined score.

An Item begins at its selected heading and ends at the next selected heading. The final Item ends at `SIGNATURES` when that marker exists, otherwise at the end of the normalized document.

The returned value is a list of dictionaries in document order:

```python
[
    {
        "item": "1A",
        "title": "RISK FACTORS",
        "content": "...",
        "content_html": "<h3>ITEM 1A. RISK FACTORS</h3><p>...</p>",
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

The content is always a direct slice of normalized source text:

```python
content == normalized_text[start:end]
```

`content_html` is a sanitized presentation representation. HTML tables preserve their rows, cells, `colspan`, and `rowspan`, while `content` remains unchanged for offsets and confidence evaluation.

Initial live SEC tests:

| Filing | Format | Items found | Filing confidence |
|---|---|---:|---:|
| Coca-Cola 2025 10-K | HTML | 23 of 23 expected | 0.954 |
| Coca-Cola 1994 10-K405 | Complete-submission TXT | 14 of 14 expected | 0.952 |

These scores evaluate structural consistency under the current heuristics. They are not yet calibrated probabilities or proof that every character boundary is correct.

### Layer 2: Small Language Model

If the Layer 1 result does not meet the confidence threshold, a small language model re-extracts the Item boundaries from the same filing.

The model should preferably return line numbers, node IDs, or other markers that map back to the source document. The program can then slice the original source using those markers. This avoids having the model summarize, rewrite, or omit filing content.

### Layer 3: Large Language Model

If the small model's result still does not meet the threshold, a more capable language model handles difficult cases such as nonstandard headings, confusion between a table of contents and the body, old SEC document formats, or damaged document structures.

This is the final fallback. Its result is returned even if its confidence remains below the acceptance threshold, with an explicit warning that manual review is recommended.
