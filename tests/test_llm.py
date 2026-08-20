"""Tests for the llm module."""

import pytest
import json
import os
from unittest.mock import patch, MagicMock
from app.llm import (
    llm_is_configured,
    _model,
    _client,
    _parse_json,
    _chat_json,
    _findings_text,
    _research_text,
    _financial_text,
    discover_competitors,
    build_thesis_with_llm,
    generate_triggers_with_llm,
    evaluate_with_llm,
    assess_findings_with_llm,
)


class TestLLMConfiguration:
    """Test LLM configuration checks."""

    def test_llm_is_configured(self):
        # Depends on environment
        result = llm_is_configured()
        assert isinstance(result, bool)

    def test_model_name(self):
        model = _model()
        assert isinstance(model, str)
        assert len(model) > 0

    def test_client_creation(self):
        if llm_is_configured():
            client = _client()
            assert client is not None


class TestJSONParsing:
    """Test JSON parsing utilities."""

    def test_parse_json_clean(self):
        result = _parse_json('{"key": "value", "number": 123}')
        assert result == {"key": "value", "number": 123}

    def test_parse_json_with_code_fence(self):
        result = _parse_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_with_python_fence(self):
        # The function only handles ```json``` or ``` fences, not ```python```
        # This test verifies it raises JSONDecodeError for python fences
        with pytest.raises(json.JSONDecodeError):
            _parse_json('```python\n{"key": "value"}\n```')

    def test_parse_json_with_whitespace(self):
        result = _parse_json('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}


class TestHelperFunctions:
    """Test helper functions."""

    def test_findings_text(self):
        findings = [
            {"agent": "News Agent", "status": "Live", "impact": "Positive", "source": "Google News", "finding": "Company beats earnings"},
            {"agent": "Financial Agent", "status": "Live", "impact": "Positive", "source": "Yahoo Finance", "finding": "Revenue up 20%"},
        ]

        text = _findings_text(findings)

        assert "News Agent" in text
        assert "Live" in text
        assert "Positive" in text
        assert "Company beats earnings" in text
        assert "Financial Agent" in text
        assert "Revenue up 20%" in text

    def test_findings_text_empty(self):
        text = _findings_text([])
        assert "No agent findings available" in text

    def test_research_text(self):
        research = {
            "name": "Test Company",
            "ticker": "TEST.NS",
            "exchange": "NSE",
            "industry": "Technology",
            "market": {"price": 100, "change_percent": 2.5},
            "history": {
                "low_52w": 80,
                "high_52w": 120,
                "change_1m_pct": 5.0,
                "change_6m_pct": 10.0,
                "change_1y_pct": 15.0,
                "ytd_change_pct": 12.0,
            },
            "summary": "Test company summary",
            "competitors": [{"company": "Competitor A"}, {"company": "Competitor B"}],
            "financials": {"status": "Live", "performance": {}, "health": {}, "cash_flow": {}},
            "headlines": [
                {"title": "Headline 1", "source": "News", "impact": "Positive"},
                {"title": "Headline 2", "source": "News", "impact": "Negative"},
            ],
        }

        text = _research_text(research)

        assert "Test Company" in text
        assert "TEST.NS" in text
        assert "Technology" in text
        assert "100" in text
        assert "2.5" in text
        assert "80" in text
        assert "120" in text
        assert "Test company summary" in text
        assert "Competitor A" in text
        assert "Headline 1" in text

    def test_financial_text_live(self):
        financials = {
            "status": "Live",
            "performance": {
                "revenue": {"TTM": 100000000000},
                "revenue_growth": {"TTM": 10.5},
                "gross_margin": {"TTM": 40.0},
                "operating_margin": {"TTM": 15.2},
                "net_income": {"TTM": 10000000000},
                "eps": {"TTM": 50.0},
            },
            "health": {
                "cash": {"TTM": 50000000000},
                "debt": {"TTM": 20000000000},
                "net_debt": {"TTM": -30000000000},
            },
            "cash_flow": {
                "operating_cash_flow": {"TTM": 20000000000},
                "free_cash_flow": {"TTM": 15000000000},
                "fcf_margin": {"TTM": 15.0},
            },
        }

        text = _financial_text(financials)

        assert "Financials (TTM where noted)" in text
        assert "Revenue:" in text
        assert "operating margin" in text.lower()  # Case insensitive
        assert "Net income" in text
        assert "Cash:" in text
        assert "debt:" in text.lower()  # Case insensitive
        assert "FCF" in text  # Output uses FCF abbreviation

    def test_financial_text_unavailable(self):
        financials = {"status": "Unavailable"}
        text = _financial_text(financials)
        assert "Financials: unavailable" in text


class TestDiscoverCompetitors:
    """Test competitor discovery."""

    def test_discover_competitors_no_llm(self):
        # Test without LLM (or mock)
        with patch("app.llm.llm_is_configured", return_value=False):
            result = discover_competitors("Test Company", "Technology", "TEST.NS")
            assert result == []

    @patch("app.llm._chat_json")
    def test_discover_competitors_with_llm(self, mock_chat):
        mock_chat.return_value = {
            "competitors": [
                {
                    "company": "Competitor A",
                    "ticker": "COMPA.NS",
                    "reason": "Direct competitor",
                    "competitive_overlap": "Same market",
                    "threat_level": "High",
                },
                {
                    "company": "Competitor B",
                    "ticker": "COMPB.NS",
                    "reason": "Similar products",
                    "competitive_overlap": "Overlapping customers",
                    "threat_level": "Medium",
                },
            ]
        }

        with patch("app.llm.llm_is_configured", return_value=True):
            result = discover_competitors("Test Company", "Technology", "TEST.NS")

            assert len(result) == 2
            assert result[0]["company"] == "Competitor A"
            assert result[0]["threat_level"] == "High"
            assert result[1]["company"] == "Competitor B"


class TestBuildThesisWithLLM:
    """Test LLM thesis building."""

    @patch("app.llm._chat_json")
    def test_build_thesis_with_llm(self, mock_chat):
        mock_chat.return_value = {
            "company": "Test Company",
            "industry": "Technology",
            "bull_case": [
                {"factor": "Strong Growth", "explanation": "Revenue growing", "evidence": "Revenue +20%", "additional_evidence": "", "importance": "High"},
            ],
            "bear_case": [
                {"factor": "High Valuation", "explanation": "Stock expensive", "evidence": "P/E 50x", "additional_evidence": "", "importance": "Medium"},
            ],
            "base_case": "Balanced view",
            "confidence": 80,
            "confidence_explanation": "Good evidence",
            "assumptions": ["Assumption 1"],
            "challenge": "Key risk",
            "competitors": ["Competitor A"],
            "drivers": [
                {"name": "Revenue Growth", "description": "Revenue growing", "importance": 8, "direction": "Positive", "monitoring_required": True, "source_type": "Financial statements"},
            ],
        }

        with patch("app.llm.llm_is_configured", return_value=True):
            research = {"name": "Test Company", "ticker": "TEST.NS", "industry": "Technology", "headlines": [], "source_statuses": ["Live"]}
            findings = []

            thesis = build_thesis_with_llm(research, findings)

            assert thesis is not None
            assert thesis.company == "Test Company"
            assert thesis.industry == "Technology"
            assert thesis.confidence == 80
            assert len(thesis.bull_case) == 1
            assert len(thesis.bear_case) == 1
            assert len(thesis.drivers) == 1
            assert thesis.drivers[0].name == "Revenue Growth"
            assert thesis.drivers[0].importance == 8


class TestGenerateTriggersWithLLM:
    """Test LLM trigger generation."""

    @patch("app.llm._chat_json")
    def test_generate_triggers_with_llm(self, mock_chat):
        mock_chat.return_value = {
            "triggers": [
                {
                    "category": "Negative",
                    "description": "Revenue growth falls below 5%",
                    "confidence": 85,
                    "importance": "Critical",
                    "related_driver": "Revenue Growth",
                    "monitoring_frequency": "Weekly",
                    "data_source": "yahoo_finance_financials",
                    "threshold": "TTM revenue growth < 5%",
                    "current_value": "+8.2%",
                    "condition": {
                        "condition_type": "financial_metric",
                        "metric_name": "revenue_growth_ttm",
                        "operator": "<",
                        "threshold": 5.0,
                        "unit": "percent",
                        "lookback_periods": 2,
                        "period_type": "quarterly",
                        "consecutive": True,
                        "allow_gaps": True,
                        "data_source": "yahoo_finance_financials",
                    },
                }
            ]
        }

        with patch("app.llm.llm_is_configured", return_value=True):
            from app.models import Thesis, ThesisPoint, Driver

            thesis = Thesis(
                company="Test Company",
                industry="Technology",
                bull_case=[ThesisPoint(factor="Growth", explanation="", evidence="", importance="High")],
                bear_case=[],
                base_case="Test",
                confidence=80,
                assumptions=[],
                challenge="Test",
                drivers=[
                    Driver("Revenue Growth", "Revenue growing", 8, "Positive", True, "Financial statements"),
                ],
                competitors=[],
            )

            triggers = generate_triggers_with_llm(thesis, [])

            assert triggers is not None
            assert len(triggers) == 1
            assert triggers[0].category == "Negative"
            assert triggers[0].condition is not None
            assert triggers[0].condition["condition_type"] == "financial_metric"


class TestEvaluateWithLLM:
    """Test LLM event evaluation."""

    @patch("app.llm._chat_json")
    def test_evaluate_with_llm(self, mock_chat):
        mock_chat.return_value = {
            "outcome": "Positive development",
            "impact": "Positive",
            "confidence": 85,
            "recommendation": "Consider increasing position",
            "evidence": "Strong earnings beat",
            "matched_trigger_ids": ["TRG-001"],
        }

        with patch("app.llm.llm_is_configured", return_value=True):
            from app.models import Thesis, Trigger

            thesis = Thesis(
                company="Test Company",
                industry="Technology",
                bull_case=[],
                bear_case=[],
                base_case="Test",
                confidence=70,
                assumptions=[],
                challenge="Test",
                drivers=[],
                competitors=[],
            )

            triggers = [
                Trigger("TRG-001", "Negative", "Revenue decline", 80, "High", "Revenue Growth", "Test Company", "Technology", "Daily"),
            ]

            result, matched = evaluate_with_llm("Test Company beats earnings", thesis, triggers)

            assert result is not None
            assert result["outcome"] == "Positive development"
            assert result["impact"] == "Positive"
            assert result["confidence"] == 85
            assert len(matched) == 1
            assert matched[0].trigger_id == "TRG-001"


class TestAssessFindingsWithLLM:
    """Test LLM findings assessment."""

    @patch("app.llm._chat_json")
    def test_assess_findings_with_llm(self, mock_chat):
        mock_chat.return_value = {
            "stance": "Improving",
            "impact": "Positive",
            "confidence": 80,
            "recommendation": "Monitor for further strength",
            "evidence": "Multiple positive signals",
            "live_sources": 5,
            "positive_signals": 3,
            "negative_signals": 1,
            "matched_trigger_ids": [],
        }

        with patch("app.llm.llm_is_configured", return_value=True):
            from app.models import Thesis, Trigger

            thesis = Thesis(
                company="Test Company",
                industry="Technology",
                bull_case=[],
                bear_case=[],
                base_case="Test",
                confidence=70,
                assumptions=[],
                challenge="Test",
                drivers=[],
                competitors=[],
            )

            triggers = []
            findings = [
                {"agent": "News Agent", "status": "Live", "impact": "Positive", "finding": "Positive news"},
            ]

            result = assess_findings_with_llm(findings, thesis, triggers)

            assert result is not None
            assert result["stance"] == "Improving"
            assert result["impact"] == "Positive"
            assert result["confidence"] == 80


if __name__ == "__main__":
    pytest.main([__file__, "-v"])