"""Tests for the analyst module."""

import pytest
from unittest.mock import patch
from app.analyst import (
    build_thesis,
    company_snapshot,
    generate_triggers,
    evaluate_event,
    summarize_thesis,
    drivers_rows,
    trigger_rows,
    _headline_signal,
    _driver_title,
)
from app.models import Thesis, ThesisPoint, Trigger, Driver


class TestHelperFunctions:
    """Test helper functions."""

    def test_headline_signal_positive(self):
        assert _headline_signal("Company reports strong profit growth") > 0
        assert _headline_signal("Stock rises on earnings beat") > 0

    def test_headline_signal_negative(self):
        assert _headline_signal("Company reports massive loss and debt") < 0
        assert _headline_signal("Stock falls on probe announcement") < 0

    def test_headline_signal_neutral(self):
        assert _headline_signal("Company holds annual meeting") == 0
        assert _headline_signal("Board meets to discuss strategy") == 0

    def test_driver_title(self):
        title = _driver_title("Company Reports Strong Growth - Yahoo Finance")
        assert "Yahoo Finance" not in title
        assert "Company Reports Strong Growth" in title


class TestBuildThesis:
    """Test thesis building."""

    def test_build_thesis_structure(self):
        research = {
            "name": "Test Company",
            "ticker": "TEST.NS",
            "industry": "Technology",
            "headlines": [
                {"title": "Test Company reports strong growth", "source": "News", "impact": "Positive"},
                {"title": "Test Company faces regulatory probe", "source": "News", "impact": "Negative"},
            ],
            "source_statuses": ["Live", "Live"],
            "market": {"price": 100, "change_percent": 2.5},
            "history": {"low_52w": 80, "high_52w": 120, "change_1y_pct": 15},
        }
        findings = []

        thesis = build_thesis("Test Company", "TEST.NS", research, findings)

        assert isinstance(thesis, Thesis)
        assert thesis.company == "Test Company"
        assert thesis.industry == "Technology"
        assert 15 <= thesis.confidence <= 90
        assert len(thesis.bull_case) >= 1
        assert len(thesis.bear_case) >= 1
        assert len(thesis.drivers) >= 1
        assert len(thesis.assumptions) >= 1  # At least 1 assumption
        assert thesis.challenge is not None
        assert len(thesis.competitors) >= 0

    def test_build_thesis_with_financials(self):
        from app.financial_agent import FinancialSnapshot

        research = {
            "name": "Test Company",
            "ticker": "TEST.NS",
            "industry": "Technology",
            "headlines": [],
            "source_statuses": ["Live"],
            "market": {"price": 100, "change_percent": 2.5},
            "history": {"low_52w": 80, "high_52w": 120, "change_1y_pct": 15},
            "financials": {
                "status": "Live",
                "performance": {
                    "revenue": {"TTM": 1000000000, "FY-1": 900000000},
                    "revenue_growth": {"TTM": 10.5},
                    "operating_margin": {"TTM": 15.2},
                    "net_income": {"TTM": 100000000},
                    "eps": {"TTM": 5.0},
                    "eps_growth": {"TTM": 12.0},
                },
                "health": {
                    "cash": {"TTM": 500000000},
                    "debt": {"TTM": 200000000},
                    "net_debt": {"TTM": -300000000},
                    "debt_to_equity": {"TTM": 0.3},
                },
                "cash_flow": {
                    "free_cash_flow": {"TTM": 150000000},
                    "fcf_margin": {"TTM": 15.0},
                },
            },
        }
        findings = []

        thesis = build_thesis("Test Company", "TEST.NS", research, findings)

        # Should have financial drivers
        financial_drivers = [d for d in thesis.drivers if d.source_type == "Financial statements"]
        assert len(financial_drivers) >= 2

        # Should have financial signals in bull/bear
        bull_factors = [p.factor for p in thesis.bull_case]
        bear_factors = [p.factor for p in thesis.bear_case]
        assert any("Financial" in f or "Revenue" in f or "Margin" in f for f in bull_factors + bear_factors)


class TestCompanySnapshot:
    """Test company snapshot generation."""

    def test_company_snapshot(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[],
            bear_case=[],
            base_case="Test base case",
            confidence=70,
            assumptions=["Test assumption"],
            challenge="Test challenge",
            drivers=[],
            competitors=[],
        )

        research = {
            "ticker": "TEST.NS",
            "exchange": "NSE",
            "market": {"price": 100, "change_percent": 2.5},
            "history": {"low_52w": 80, "high_52w": 120, "change_1y_pct": 15, "ytd_change_pct": 10},
            "sources": ["Yahoo Finance", "Wikipedia"],
            "summary": "Test company summary",
        }

        snapshot = company_snapshot(thesis, research)

        assert "Resolved company" in snapshot
        assert "Ticker" in snapshot
        assert "Exchange" in snapshot
        assert "Classification" in snapshot
        assert "Latest market observation" in snapshot
        assert "52-week range" in snapshot
        assert "1-year performance" in snapshot
        assert "Live sources" in snapshot
        assert snapshot["Resolved company"] == "Test Company"
        assert snapshot["Ticker"] == "TEST.NS"


class TestGenerateTriggers:
    """Test trigger generation."""

    def test_generate_triggers_fallback(self):
        # Mock LLM to force fallback behavior
        with patch("app.llm.generate_triggers_with_llm", return_value=None):
            thesis = Thesis(
                company="Test Company",
                industry="Technology",
                bull_case=[],
                bear_case=[],
                base_case="Test base case",
                confidence=70,
                assumptions=["Test assumption"],
                challenge="Test challenge",
                drivers=[
                    Driver("Revenue growth", "Revenue is growing", 8, "Positive", True, "Financial statements"),
                    Driver("Market share", "Market share is stable", 6, "Neutral", True, "Market data"),
                    Driver("Regulatory risk", "Regulatory risk is high", 9, "Negative", True, "Live news"),
                ],
                competitors=["Competitor A"],
            )

            triggers = generate_triggers(thesis, [])

            assert len(triggers) == 3
            for trigger in triggers:
                assert isinstance(trigger, Trigger)
                assert trigger.trigger_id.startswith("TRG-")
                assert trigger.category in ("Positive", "Negative", "Hold")
                assert trigger.confidence >= 40
                assert trigger.importance in ("Critical", "High", "Medium")
                assert trigger.monitoring_frequency in ("Hours", "Daily", "Weekly", "Monthly")
                assert trigger.status == "Monitoring"

    def test_trigger_categories_match_driver_direction(self):
        # Mock LLM to force fallback behavior
        with patch("app.llm.generate_triggers_with_llm", return_value=None):
            thesis = Thesis(
                company="Test Company",
                industry="Technology",
                bull_case=[],
                bear_case=[],
                base_case="Test base case",
                confidence=70,
                assumptions=["Test assumption"],
                challenge="Test challenge",
                drivers=[
                    Driver("Positive driver", "Description", 8, "Positive", True, "Source"),
                    Driver("Negative driver", "Description", 8, "Negative", True, "Source"),
                    Driver("Neutral driver", "Description", 5, "Neutral", True, "Source"),
                ],
                competitors=[],
            )

            triggers = generate_triggers(thesis, [])

            # Find triggers by related_driver
            pos_trigger = next((t for t in triggers if "Positive" in t.related_driver), None)
            neg_trigger = next((t for t in triggers if "Negative" in t.related_driver), None)
            neu_trigger = next((t for t in triggers if "Neutral" in t.related_driver), None)

            # Fallback behavior: category matches driver direction
            # Positive driver -> Positive category
            if pos_trigger:
                assert pos_trigger.category == "Positive"

            # Negative driver -> Negative category
            if neg_trigger:
                assert neg_trigger.category == "Negative"

            # Neutral driver -> Hold category
            if neu_trigger:
                assert neu_trigger.category == "Hold"


class TestEvaluateEvent:
    """Test event evaluation."""

    def test_evaluate_event_positive(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[ThesisPoint(factor="Strong growth", explanation="", evidence="", importance="High")],
            bear_case=[],
            base_case="Test base case",
            confidence=70,
            assumptions=["Test"],
            challenge="Test",
            drivers=[
                Driver("Revenue growth", "Revenue growing", 8, "Positive", True, "Financial statements"),
            ],
            competitors=[],
        )

        triggers = [
            Trigger("TRG-TEST1", "Negative", "Revenue declines", 80, "High", "Revenue growth", "Test Company", "Technology", "Daily"),
        ]

        result, activated = evaluate_event(
            "Test Company reports record quarterly revenue and strong growth",
            thesis,
            triggers,
        )

        assert result["impact"] == "Positive"
        assert result["confidence"] >= 50
        assert "outcome" in result
        assert "recommendation" in result
        assert "evidence" in result

    def test_evaluate_event_negative(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[],
            bear_case=[ThesisPoint(factor="High debt", explanation="", evidence="", importance="High")],
            base_case="Test base case",
            confidence=70,
            assumptions=["Test"],
            challenge="Test",
            drivers=[
                Driver("Debt levels", "Debt is high", 9, "Negative", True, "Financial statements"),
            ],
            competitors=[],
        )

        triggers = [
            Trigger("TRG-TEST1", "Positive", "Debt increases", 85, "Critical", "Debt levels", "Test Company", "Technology", "Daily"),
        ]

        result, activated = evaluate_event(
            "Test Company debt increases significantly in latest quarter",
            thesis,
            triggers,
        )

        assert result["impact"] == "Negative"
        assert result["confidence"] >= 50

    def test_evaluate_event_unclear(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[],
            bear_case=[],
            base_case="Test base case",
            confidence=70,
            assumptions=["Test"],
            challenge="Test",
            drivers=[],
            competitors=[],
        )

        triggers = []

        result, activated = evaluate_event(
            "Test Company holds annual general meeting",
            thesis,
            triggers,
        )

        assert result["impact"] in ("Unclear", "Neutral")
        assert "outcome" in result


class TestSummarizeThesis:
    """Test thesis summarization."""

    def test_summarize_thesis(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[
                ThesisPoint(factor="Strong Growth", explanation="Revenue growing fast", evidence="Revenue +20%", importance="High"),
            ],
            bear_case=[
                ThesisPoint(factor="High Valuation", explanation="Stock expensive", evidence="P/E 50x", importance="Medium"),
            ],
            base_case="Test base case",
            confidence=75,
            assumptions=["Assumption 1", "Assumption 2"],
            challenge="Key risk",
            drivers=[],
            competitors=["Competitor A", "Competitor B"],
        )

        summary = summarize_thesis(thesis)

        assert "Test Company" in summary
        assert "Technology" in summary
        assert "75" in summary
        assert "Base case" in summary
        assert "Bull case" in summary
        assert "Bear case" in summary
        assert "Critical assumptions" in summary
        assert "What could prove this wrong?" in summary
        assert "Competitors" in summary
        assert "Strong Growth" in summary
        assert "High Valuation" in summary


class TestFormattingFunctions:
    """Test formatting functions for UI."""

    def test_drivers_rows(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[],
            bear_case=[],
            base_case="Test",
            confidence=70,
            assumptions=[],
            challenge="Test",
            drivers=[
                Driver("Driver 1", "Description 1", 8, "Positive", True, "Source 1"),
                Driver("Driver 2", "Description 2", 6, "Negative", False, "Source 2"),
            ],
            competitors=[],
        )

        rows = drivers_rows(thesis)

        assert len(rows) == 2
        assert rows[0][0] == "Driver 1"
        assert rows[0][2] == 8
        assert rows[0][3] == "Positive"
        assert rows[0][4] == "Yes"
        assert rows[1][0] == "Driver 2"
        assert rows[1][3] == "Negative"
        assert rows[1][4] == "No"

    def test_trigger_rows(self):
        triggers = [
            Trigger("TRG-001", "Negative", "Description 1", 80, "High", "Driver 1", "Company", "Industry", "Daily"),
            Trigger("TRG-002", "Positive", "Description 2", 75, "Medium", "Driver 2", "Company", "Industry", "Weekly"),
        ]

        rows = trigger_rows(triggers)

        assert len(rows) == 2
        assert rows[0][0] == "TRG-001"
        assert rows[0][1] == "Negative"
        assert rows[0][3] == 80
        assert rows[0][4] == "High"
        assert rows[0][6] == "Daily"  # monitoring_frequency is at index 6
        assert rows[1][6] == "Weekly"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])