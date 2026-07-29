"""Tests for deterministic confidence calculations."""

import unittest

from app.evaluations.confidence_evaluator import (
    HeadingCandidate,
    calculate_filing_confidence,
    calculate_heading_confidence,
)


class ConfidenceEvaluatorTests(unittest.TestCase):
    def test_standard_heading(self) -> None:
        candidate = HeadingCandidate(
            text="ITEM 1A. RISK FACTORS",
            expected_item="1A",
            expected_title="Risk Factors",
            is_own_dom_block=True,
        )
        self.assertEqual(calculate_heading_confidence(candidate), 1.0)

    def test_subitem_is_not_a_main_item_heading(self) -> None:
        candidate = HeadingCandidate(
            text="ITEM 14(a)2",
            expected_item="14",
        )
        self.assertEqual(calculate_heading_confidence(candidate), 0.0)

    def test_filing_confidence_is_average(self) -> None:
        self.assertEqual(
            calculate_filing_confidence([0.95, 0.90, 0.85]),
            0.90,
        )

    def test_empty_filing_confidence_is_zero(self) -> None:
        self.assertEqual(calculate_filing_confidence([]), 0.0)
