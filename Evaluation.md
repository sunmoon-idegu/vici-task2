# Evaluation

## Item-Level Confidence

Each extracted Item is evaluated using three signals:

```text
item_confidence =
    weighted combination of:
    - heading
    - body_vs_toc
    - section
```

The three Item-level signals answer different questions:

- `heading`: Does the candidate block look like an Item heading?
- `body_vs_toc`: Is this the body heading rather than an entry in a table of contents?
- `section`: Is the extracted content between this Item and the next Item plausibly bounded?

All signals and resulting confidence scores are between `0` and `1`.

The `heading` calculation is defined below. The exact Item-level weights and calculations for `body_vs_toc` and `section` are still to be discussed and finalized.

### Heading Confidence

Heading confidence answers one narrow question: does a candidate block look like an Item heading?

For each candidate block:

```text
heading_confidence =
    0.70 × item_identifier
  + 0.20 × heading_format
  + 0.10 × title_similarity
```

#### Item Identifier

`item_identifier` is binary: `0` or `1`.

The candidate block must begin with a valid Item identifier.

```text
ITEM 1A. RISK FACTORS → 1
See Item 1A           → 0
```

#### Heading Format

```text
heading_format =
    0.4 × is_short
  + 0.3 × is_isolated
  + 0.3 × is_emphasized
```

Each component is binary:

- `is_short`: the normalized candidate text is no longer than 120 characters.
- `is_isolated`: the candidate is its own DOM block or has a blank line before or after it.
- `is_emphasized`: the candidate uses an HTML heading tag, is bold, or is mostly uppercase.

Example:

```text
ITEM 1A. RISK FACTORS
```

If it is short, isolated, and uppercase:

```text
heading_format = 0.4 + 0.3 + 0.3 = 1.0
```

#### Title Similarity

`title_similarity` is between `0` and `1`.

The detected and expected titles are first normalized:

- Convert to lowercase.
- Replace punctuation with spaces.
- Collapse repeated whitespace.

The normalized strings are compared using Python's `difflib.SequenceMatcher`, which is based on the Ratcliff/Obershelp pattern-matching algorithm. This is deterministic string matching, not machine learning.

Examples:

```text
Risk Factors    vs Risk Factors → 1.0
Risk-Factors    vs Risk Factors → 1.0
empty title     vs Risk Factors → 0.0
```

Exact title wording is only supporting evidence because titles and Item structures may vary across filing periods.

#### Heading Examples

```text
ITEM 1A. RISK FACTORS
```

```text
item_identifier = 1.0
heading_format  = 1.0
title_similarity = 1.0

heading_confidence = 1.0
```

```text
ITEM 1A.
```

```text
item_identifier = 1.0
heading_format  = 1.0
title_similarity = 0.0

heading_confidence = 0.90
```

```text
See Item 1A for details
```

```text
item_identifier = 0.0
heading_confidence = 0.0
```

This score does not determine whether the candidate is a body heading or a table-of-contents entry. That requires a separate confidence component.

### Body-versus-TOC Confidence

This signal evaluates whether the selected heading belongs to the filing body rather than a table of contents.

For each heading candidate:

```text
body_vs_toc =
    0.35 × content_after
  + 0.30 × no_toc_format
  + 0.20 × low_heading_density
  + 0.15 × no_later_duplicate
```

#### Content After

Count the characters between the candidate and the next Item heading candidate:

```text
500 or more characters → 1.0
100–499 characters     → 0.5
Fewer than 100         → 0.0
```

TOC entries usually have very little content between adjacent headings.

#### No TOC Format

The candidate has TOC formatting when it:

- Ends with a page number.
- Contains dot leaders such as `........ 25`.
- Is only an HTML link.

```text
TOC formatting detected → 0.0
No TOC formatting       → 1.0
```

Examples:

```text
Item 1A. Risk Factors ........ 25 → 0.0
Item 1A. Risk Factors            → 1.0
```

#### Low Heading Density

Count other Item heading candidates within the next 1,000 characters:

```text
0–2 candidates → 1.0
3–4 candidates → 0.5
5 or more      → 0.0
```

A TOC usually contains many Item headings close together.

#### No Later Duplicate

Check whether another strong candidate for the same Item appears later in the document:

```text
Later duplicate exists → 0.0
No later duplicate     → 1.0
```

If `Item 1A` appears near the beginning and again much later, the first occurrence is likely a TOC entry.

#### Example

For:

```text
Item 1A. Risk Factors ........ 25
Item 1B. Unresolved Staff Comments ........ 40
```

a likely evaluation is:

```text
content_after       = 0.0
no_toc_format       = 0.0
low_heading_density = 0.0
no_later_duplicate  = 0.0

body_vs_toc = 0.0
```

### Section Confidence

Section confidence answers:

> Does `start` and `end` correctly surround this Item's content?

For each extracted Item:

```text
section_confidence =
    0.40 × end_boundary
  + 0.40 × no_skipped_heading
  + 0.20 × content_present
```

#### End Boundary

An Item normally ends where the next selected Item heading begins.

Use the heading confidence of that next Item:

```text
end_boundary = heading confidence of the next selected Item
```

For the final Item, a recognized terminal marker such as `SIGNATURES` may receive `1.0`.

#### No Skipped Heading

Check whether another strong, unselected Item heading appears between `start` and `end`:

```text
No unselected heading         → 1.0
One uncertain heading         → 0.5
Strong unselected heading     → 0.0
```

For example, if Item 1A ends at Item 2 but a strong Item 1B heading exists between them, Item 1A probably has the wrong end boundary.

#### Content Present

```text
100 or more characters                   → 1.0
Recognized short response such as `None` → 1.0
Other content below 100 characters       → 0.5
Empty content                            → 0.0
```

Valid short responses may also include `Not applicable` or an incorporation-by-reference statement.

#### Hard Failures

These conditions set section confidence to `0`:

```text
start >= end
section overlaps another extracted Item
content != source[start:end]
```

#### Examples

Correctly bounded Item:

```text
end_boundary      = 0.98
no_skipped_heading = 1.00
content_present    = 1.00

section_confidence =
    0.40 × 0.98
  + 0.40 × 1.00
  + 0.20 × 1.00
  = 0.992
```

Item 1B was accidentally included inside Item 1A:

```text
end_boundary       = 0.97
no_skipped_heading = 0.00
content_present    = 1.00

section_confidence =
    0.40 × 0.97
  + 0.40 × 0.00
  + 0.20 × 1.00
  = 0.588
```

Valid short section:

```text
ITEM 1B. UNRESOLVED STAFF COMMENTS
None.
ITEM 1C. CYBERSECURITY
```

```text
end_boundary       = 0.95
no_skipped_heading = 1.00
content_present    = 1.00

section_confidence = 0.98
```

## Filing Confidence

The filing-level confidence determines whether the current extraction layer is accepted or whether the pipeline continues to the next layer.

First, calculate the average confidence across all extracted Items:

```text
average_item_confidence =
    sum(item_confidence) / number_of_items
```

### Sequence Confidence

Sequence confidence describes whether all extracted Items appear in a valid order. Calculate it from adjacent Item pairs in source order:

```text
sequence_confidence =
    valid_adjacent_pairs / total_adjacent_pairs
```

Missing Items are allowed when the remaining Items are in valid order.

```text
["1", "1A", "2", "3"]   → valid
["1", "2", "1A", "3"]   → invalid ordering
["1", "1A", "1A", "2"]  → duplicate Item
```

The initial filing-level formula is:

```text
filing_confidence =
    average_item_confidence × sequence_confidence
```

Examples:

```text
average_item_confidence = 0.95
sequence_confidence     = 1.00
filing_confidence       = 0.95
```

```text
average_item_confidence = 0.95
sequence_confidence     = 0.67
filing_confidence       = 0.637
```

### Sequential Fallback

The sequential fallback rule is:

```text
Layer 1 confidence >= threshold → return Layer 1
Layer 1 confidence <  threshold → run Layer 2

Layer 2 confidence >= threshold → return Layer 2
Layer 2 confidence <  threshold → run Layer 3

Layer 3 → always return
```

The provisional threshold is `0.90`. It must be calibrated using labeled examples before being interpreted as a probability of correctness.
