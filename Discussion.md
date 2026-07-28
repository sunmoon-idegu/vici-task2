# Design Discussion

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

Layer 1 uses regular expressions, DOM or text structure, and Part and Item ordering to identify Item boundaries according to the characteristics of HTML and TXT inputs. It is the fastest and least expensive extraction method and is expected to handle most filings with recognizable structures.

### Layer 2: Small Language Model

If the Layer 1 result does not meet the confidence threshold, a small language model re-extracts the Item boundaries from the same filing.

The model should preferably return line numbers, node IDs, or other markers that map back to the source document. The program can then slice the original source using those markers. This avoids having the model summarize, rewrite, or omit filing content.

### Layer 3: Large Language Model

If the small model's result still does not meet the threshold, a more capable language model handles difficult cases such as nonstandard headings, confusion between a table of contents and the body, old SEC document formats, or damaged document structures.

This is the final fallback. Its result is returned even if its confidence remains below the acceptance threshold, with an explicit warning that manual review is recommended.
