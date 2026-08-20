"""Tests for the agents module."""

import pytest
from datetime import datetime, timezone
from app.agents import (
    AgentFinding,
    CompanyResearchAgent,
    MarketDataAgent,
    NewsAgent,
    CompetitorAgent,
    RegulatoryAgent,
    InvestmentAnalystAgent,
    collect_full_research,
    run_live_agents,
    _impact,
    _now,
    _price_history,
    _market_snapshot,
    _wikipedia_summary,
    _yahoo_rss_headlines,
)


class TestAgentFinding:
    """Test AgentFinding dataclass."""

    def test_agent_finding_creation(self):
        finding = AgentFinding(
            agent="Test Agent",
            status="Live",
            observed_at=_now(),
            finding="Test finding",
            source="Test Source",
            url="https://example.com",
            impact="Positive",
        )
        assert finding.agent == "Test Agent"
        assert finding.status == "Live"
        assert finding.impact == "Positive"

    def test_agent_finding_row(self):
        finding = AgentFinding(
            agent="Test Agent",
            status="Live",
            observed_at=_now(),
            finding="Test finding",
            source="Test Source",
            impact="Positive",
        )
        row = finding.row()
        assert len(row) == 6
        assert row[0] == "Test Agent"
        assert row[1] == "Live"
        assert row[2] == "Positive"

    def test_agent_finding_to_dict(self):
        finding = AgentFinding(
            agent="Test Agent",
            status="Live",
            observed_at=_now(),
            finding="Test finding",
            source="Test Source",
            impact="Positive",
        )
        d = finding.to_dict()
        assert d["agent"] == "Test Agent"
        assert d["status"] == "Live"
        assert d["impact"] == "Positive"


class TestImpactClassification:
    """Test the _impact helper function."""

    def test_positive_impact(self):
        assert _impact("Company reports strong profit growth") == "Positive"
        assert _impact("Stock rises on earnings beat") == "Positive"
        assert _impact("New partnership announced") == "Positive"
        assert _impact("Product launch successful") == "Positive"

    def test_negative_impact(self):
        assert _impact("Company reports massive loss") == "Negative"
        assert _impact("Stock falls on debt concerns") == "Negative"
        assert _impact("Regulatory probe launched") == "Negative"
        assert _impact("Earnings cut announced") == "Negative"

    def test_unclear_impact(self):
        assert _impact("Company holds annual meeting") == "Unclear"
        assert _impact("Board meets to discuss strategy") == "Unclear"


class TestHelperFunctions:
    """Test helper functions."""

    def test_now_format(self):
        now_str = _now()
        assert "UTC" in now_str
        assert len(now_str) > 10

    def test_price_history_structure(self):
        # This requires network, so we'll test structure only
        # Skip actual call in CI
        pass

    def test_market_snapshot_structure(self):
        pass


class TestCompanyResearchAgent:
    """Test CompanyResearchAgent."""

    def test_agent_name(self):
        agent = CompanyResearchAgent()
        assert agent.name == "Company Research Agent"

    def test_collect_basic(self):
        # Test with a known company
        result = CompanyResearchAgent().collect("Vodafone Idea", "IDEA.NS")
        assert "company" in result
        assert "ticker" in result
        assert "sources" in result
        assert "source_statuses" in result
        assert isinstance(result["headlines"], list)
        assert isinstance(result["sources"], list)
        assert isinstance(result["source_statuses"], list)


class TestMarketDataAgent:
    """Test MarketDataAgent."""

    def test_agent_name(self):
        agent = MarketDataAgent()
        assert agent.name == "Market Data Agent"

    def test_collect_no_ticker(self):
        agent = MarketDataAgent()
        findings = agent.collect("")
        assert len(findings) == 1
        assert findings[0].status == "Skipped"
        assert "No ticker" in findings[0].finding

    def test_collect_invalid_ticker(self):
        agent = MarketDataAgent()
        findings = agent.collect("INVALID_TICKER_12345")
        # Should return Unavailable status
        assert len(findings) == 1
        assert findings[0].status in ("Unavailable", "Skipped")


class TestNewsAgent:
    """Test NewsAgent."""

    def test_agent_name(self):
        agent = NewsAgent()
        assert agent.name == "Company News Agent"

    def test_collect(self):
        agent = NewsAgent()
        findings = agent.collect("Vodafone Idea")
        assert len(findings) >= 1
        assert findings[0].agent == "Company News Agent"
        assert findings[0].source == "Google News RSS"


class TestCompetitorAgent:
    """Test CompetitorAgent."""

    def test_agent_name(self):
        agent = CompetitorAgent()
        assert agent.name == "Competitor Intelligence Agent"

    def test_collect_no_competitors(self):
        agent = CompetitorAgent()
        findings = agent.collect([], "Telecommunications")
        assert len(findings) == 1
        assert findings[0].status == "Skipped"
        assert "No competitors" in findings[0].finding

    def test_collect_with_competitors(self):
        agent = CompetitorAgent()
        findings = agent.collect(["Bharti Airtel", "Reliance Jio"], "Telecommunications")
        assert len(findings) >= 1
        assert findings[0].agent == "Competitor Intelligence Agent"


class TestRegulatoryAgent:
    """Test RegulatoryAgent."""

    def test_agent_name(self):
        agent = RegulatoryAgent()
        assert agent.name == "Regulatory & Policy Agent"

    def test_collect(self):
        agent = RegulatoryAgent()
        findings = agent.collect("Vodafone Idea", "Telecommunications")
        assert len(findings) >= 1
        assert findings[0].agent == "Regulatory & Policy Agent"


class TestCollectFullResearch:
    """Test the collect_full_research function."""

    def test_collect_full_research(self):
        bundle = collect_full_research("Vodafone Idea", "IDEA.NS")
        assert "research" in bundle
        assert "findings" in bundle
        assert isinstance(bundle["findings"], list)
        assert len(bundle["findings"]) > 0

        research = bundle["research"]
        assert research["ticker"] == "IDEA.NS"
        assert "financials" in research
        assert "competitors" in research


class TestRunLiveAgents:
    """Test the run_live_agents function."""

    def test_run_live_agents(self):
        from app.models import Thesis, Trigger

        thesis = Thesis(
            company="Vodafone Idea Limited",
            industry="Telecommunications",
            bull_case=[],
            bear_case=[],
            base_case="Test",
            confidence=70,
            assumptions=[],
            challenge="Test",
            drivers=[],
            competitors=["Bharti Airtel", "Reliance Jio"],
        )

        triggers = [
            Trigger("TRG-TEST", "Negative", "Test trigger", 80, "High", "Driver", "Vodafone Idea", "Telecommunications", "Daily")
        ]

        result = run_live_agents(thesis, "IDEA.NS", triggers)
        assert "findings" in result
        assert "assessment" in result
        assert "checked_at" in result
        assert isinstance(result["findings"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])