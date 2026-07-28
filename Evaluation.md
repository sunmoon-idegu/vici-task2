# Evaluation

## Evaluation Structure

Evaluation happens at two levels:

1. Evaluate each extracted Item.
2. Combine the Item results into one confidence score for the complete filing extraction.

Each Item is evaluated using four signals:

```text
item_confidence =
    0.35 × heading
  + 0.30 × sequence
  + 0.20 × body_vs_toc
  + 0.15 × section
```

The four signals answer different questions:

- `heading`: Does the candidate block look like an Item heading?
- `sequence`: Is the Item in a valid position relative to the surrounding Items?
- `body_vs_toc`: Is this the body heading rather than an entry in a table of contents?
- `section`: Is the extracted content between this Item and the next Item plausibly bounded?

All signals and the resulting confidence score are between `0` and `1`.

The weights above are initial engineering values, not values learned by machine learning. They must later be tested and calibrated against a manually labeled evaluation set.

The `heading` calculation is defined below. The exact calculations for `sequence`, `body_vs_toc`, and `section` are still to be discussed and finalized.

## Heading Confidence

Heading confidence answers one narrow question: does a candidate block look like an Item heading?

For each candidate block:

```text
heading_confidence =
    0.70 × item_identifier
  + 0.20 × heading_format
  + 0.10 × title_similarity
```

### Item Identifier

`item_identifier` is binary: `0` or `1`.

The candidate block must begin with a valid Item identifier.

```text
ITEM 1A. RISK FACTORS → 1
See Item 1A           → 0
```

### Heading Format

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

### Title Similarity

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

## Complete Examples

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

## Sequence Confidence

Sequence confidence evaluates whether an Item appears in a valid order relative to the previous and next extracted Items.

For example:

```text
Item 1 → Item 1A → Item 2
```

is structurally plausible, while:

```text
Item 1A → Item 1
```

is not.

The calculation must allow valid missing or inapplicable Items. Its exact scoring rules have not yet been finalized.

## Body-versus-TOC Confidence

This signal evaluates whether the selected heading belongs to the filing body rather than a table of contents.

Possible evidence includes:

- The heading is followed by substantial body content.
- Nearby headings are not densely grouped together.
- The block does not end with a page number.
- The block is not only an internal link.
- A later occurrence of the same Item heading exists.

The exact scoring rules have not yet been finalized.

## Section Confidence

Section confidence evaluates the content extracted between the current Item heading and the next selected Item heading.

Possible evidence includes:

- The section is not empty.
- Its boundaries do not overlap another Item.
- The content is a continuous slice of the source.
- The section does not end in the middle of a paragraph.
- Its length is not clearly implausible.

A short section is not automatically incorrect because valid sections may contain only `None`, `Not applicable`, or an incorporation-by-reference statement.

The exact scoring rules have not yet been finalized.

## Filing-level Result

The filing-level confidence determines whether the current extraction layer is accepted or whether the pipeline continues to the next layer.

The initial proposal is:

```text
filing_confidence = minimum item_confidence
```

Using the minimum is intentionally conservative: one badly extracted Item is enough to escalate the complete filing.

The sequential fallback rule is:

```text
Layer 1 confidence >= threshold → return Layer 1
Layer 1 confidence <  threshold → run Layer 2

Layer 2 confidence >= threshold → return Layer 2
Layer 2 confidence <  threshold → run Layer 3

Layer 3 → always return
```

The provisional threshold is `0.90`. It must be calibrated using labeled examples before being interpreted as a probability of correctness.
