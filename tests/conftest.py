"""Pytest configuration and fixtures."""

import pytest
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    os.environ.setdefault("DATABASE_URL", "sqlite:///test_investment_intelligence.db")
    os.environ.setdefault("OPENAI_API_KEY", "")
    os.environ.setdefault("SMTP_HOST", "")
    os.environ.setdefault("SMTP_USERNAME", "")
    os.environ.setdefault("SMTP_PASSWORD", "")
    os.environ.setdefault("ALERT_RECIPIENT", "")
    os.environ.setdefault("ALERT_FROM", "")

    yield

    # Cleanup
    test_db = "test_investment_intelligence.db"
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest.fixture
def sample_thesis():
    """Create a sample thesis for testing."""
    from app.models import Thesis, ThesisPoint, Driver

    return Thesis(
        company="Test Company",
        industry="Technology",
        bull_case=[
            ThesisPoint(factor="Strong Growth", explanation="Revenue growing", evidence="Revenue +20%", importance="High"),
        ],
        bear_case=[
            ThesisPoint(factor="High Valuation", explanation="Stock expensive", evidence="P/E 50x", importance="Medium"),
        ],
        base_case="Balanced view with growth potential but valuation concerns",
        confidence=75,
        assumptions=["Market conditions remain stable", "Management executes strategy"],
        challenge="Valuation could compress if growth slows",
        drivers=[
            Driver("Revenue Growth", "Revenue growing at 20% YoY", 8, "Positive", True, "Financial statements"),
            Driver("Market Share", "Maintaining 30% market share", 6, "Neutral", True, "Market data"),
        ],
        competitors=["Competitor A", "Competitor B"],
    )


@pytest.fixture
def sample_triggers():
    """Create sample triggers for testing."""
    from app.models import Trigger

    return [
        Trigger(
            trigger_id="TRG-001",
            category="Negative",
            description="Revenue growth falls below 5%",
            confidence=85,
            importance="Critical",
            related_driver="Revenue Growth",
            related_companies="Test Company, Competitor A",
            related_industry="Technology",
            monitoring_frequency="Weekly",
            status="Monitoring",
        ),
        Trigger(
            trigger_id="TRG-002",
            category="Positive",
            description="Operating margin improves above 20%",
            confidence=80,
            importance="High",
            related_driver="Operating Margin",
            related_companies="Test Company, Competitor A",
            related_industry="Technology",
            monitoring_frequency="Weekly",
            status="Monitoring",
        ),
    ]


@pytest.fixture
def sample_findings():
    """Create sample findings for testing."""
    return [
        {"agent": "News Agent", "status": "Live", "impact": "Positive", "source": "Google News", "finding": "Company beats earnings", "observed_at": "2024-01-15 10:00:00 UTC", "url": ""},
        {"agent": "Financial Agent", "status": "Live", "impact": "Positive", "source": "Yahoo Finance", "finding": "Revenue up 20%", "observed_at": "2024-01-15 10:00:00 UTC", "url": ""},
        {"agent": "Market Data Agent", "status": "Live", "impact": "Neutral", "source": "Yahoo Finance", "finding": "Price stable", "observed_at": "2024-01-15 10:00:00 UTC", "url": ""},
    ]


@pytest.fixture
def sample_research():
    """Create sample research data for testing."""
    return {
        "company": "Test Company",
        "name": "Test Company",
        "ticker": "TEST.NS",
        "exchange": "NSE",
        "industry": "Technology",
        "headlines": [
            {"title": "Company beats earnings", "source": "Google News", "impact": "Positive", "url": ""},
            {"title": "New product launch", "source": "Yahoo Finance", "impact": "Positive", "url": ""},
        ],
        "source_statuses": ["Live", "Live", "Live"],
        "market": {"price": 100, "previous_close": 98, "change_percent": 2.0, "currency": "INR"},
        "history": {
            "low_52w": 80,
            "high_52w": 120,
            "change_1m_pct": 5.0,
            "change_3m_pct": 8.0,
            "change_6m_pct": 10.0,
            "change_1y_pct": 15.0,
            "ytd_change_pct": 12.0,
            "avg_volume_3m": 1000000,
        },
        "summary": "Test company summary",
        "competitors": [{"company": "Competitor A"}, {"company": "Competitor B"}],
        "financials": {"status": "Unavailable"},
    }


@pytest.fixture
def sample_trigger_condition():
    """Create a sample trigger condition for testing."""
    from app.models import TriggerCondition

    return TriggerCondition(
        trigger_id="TRG-TEST",
        condition_type="financial_metric",
        metric_name="revenue_growth_ttm",
        operator="<",
        threshold=5.0,
        unit="percent",
        lookback_periods=2,
        period_type="quarterly",
        consecutive=True,
        allow_gaps=True,
        data_source="yahoo_finance_financials",
    )