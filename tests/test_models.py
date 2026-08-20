"""Tests for the models module."""

import pytest
from app.models import (
    Driver,
    Trigger,
    TriggerCondition,
    MetricHistory,
    TriggerEvaluation,
    ThesisPoint,
    Thesis,
)


class TestDriver:
    """Test Driver dataclass."""

    def test_driver_creation(self):
        driver = Driver(
            name="Revenue Growth",
            description="Revenue is growing steadily",
            importance=8,
            direction="Positive",
            monitoring_required=True,
            source_type="Financial statements",
        )

        assert driver.name == "Revenue Growth"
        assert driver.importance == 8
        assert driver.direction == "Positive"
        assert driver.monitoring_required is True

    def test_driver_to_dict(self):
        driver = Driver(
            name="Test Driver",
            description="Test description",
            importance=7,
            direction="Negative",
            monitoring_required=False,
            source_type="Market data",
        )

        # Use asdict from dataclasses
        from dataclasses import asdict
        d = asdict(driver)

        assert d["name"] == "Test Driver"
        assert d["description"] == "Test description"
        assert d["importance"] == 7
        assert d["direction"] == "Negative"
        assert d["monitoring_required"] is False
        assert d["source_type"] == "Market data"


class TestTrigger:
    """Test Trigger dataclass."""

    def test_trigger_creation(self):
        trigger = Trigger(
            trigger_id="TRG-001",
            category="Negative",
            description="Revenue growth falls below 5%",
            confidence=85,
            importance="Critical",
            related_driver="Revenue growth",
            related_companies="Test Company, Competitor A",
            related_industry="Technology",
            monitoring_frequency="Weekly",
            status="Monitoring",
            condition=None,
            cooldown_until=None,
        )

        assert trigger.trigger_id == "TRG-001"
        assert trigger.category == "Negative"
        assert trigger.confidence == 85
        assert trigger.importance == "Critical"
        assert trigger.status == "Monitoring"

    def test_trigger_default_status(self):
        trigger = Trigger(
            trigger_id="TRG-001",
            category="Negative",
            description="Test",
            confidence=80,
            importance="High",
            related_driver="Test",
            related_companies="Test",
            related_industry="Test",
            monitoring_frequency="Daily",
        )

        assert trigger.status == "Monitoring"

    def test_trigger_to_dict(self):
        trigger = Trigger(
            trigger_id="TRG-001",
            category="Negative",
            description="Test trigger",
            confidence=85,
            importance="Critical",
            related_driver="Revenue growth",
            related_companies="Test Company",
            related_industry="Technology",
            monitoring_frequency="Weekly",
        )

        d = trigger.to_dict()

        assert d["trigger_id"] == "TRG-001"
        assert d["category"] == "Negative"
        assert d["confidence"] == 85
        assert d["importance"] == "Critical"
        assert d["status"] == "Monitoring"


class TestTriggerCondition:
    """Test TriggerCondition dataclass."""

    def test_trigger_condition_creation(self):
        condition = TriggerCondition(
            trigger_id="TRG-001",
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

        assert condition.trigger_id == "TRG-001"
        assert condition.condition_type == "financial_metric"
        assert condition.metric_name == "revenue_growth_ttm"
        assert condition.threshold == 5.0

    def test_trigger_condition_news_keyword(self):
        condition = TriggerCondition(
            trigger_id="TRG-002",
            condition_type="news_keyword",
            keywords=["bankruptcy", "default"],
            lookback_periods=7,
            threshold=1,
            data_source="google_news_rss",
        )

        assert condition.condition_type == "news_keyword"
        assert condition.keywords == ["bankruptcy", "default"]
        assert condition.lookback_periods == 7

    def test_trigger_condition_to_dict(self):
        condition = TriggerCondition(
            trigger_id="TRG-001",
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

        d = condition.to_dict()

        assert d["trigger_id"] == "TRG-001"
        assert d["condition_type"] == "financial_metric"
        assert d["metric_name"] == "revenue_growth_ttm"
        assert d["threshold"] == 5.0
        assert d["consecutive"] is True

    def test_trigger_condition_from_dict(self):
        data = {
            "trigger_id": "TRG-001",
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
        }

        condition = TriggerCondition.from_dict(data)

        assert condition.trigger_id == "TRG-001"
        assert condition.condition_type == "financial_metric"
        assert condition.metric_name == "revenue_growth_ttm"
        assert condition.threshold == 5.0

    def test_trigger_condition_from_dict_extra_fields(self):
        # Should ignore extra fields not in dataclass
        data = {
            "trigger_id": "TRG-001",
            "condition_type": "financial_metric",
            "metric_name": "revenue_growth_ttm",
            "extra_field": "should be ignored",
        }

        condition = TriggerCondition.from_dict(data)

        assert condition.trigger_id == "TRG-001"
        assert condition.metric_name == "revenue_growth_ttm"
        assert not hasattr(condition, "extra_field")


class TestMetricHistory:
    """Test MetricHistory dataclass."""

    def test_metric_history_creation(self):
        metric = MetricHistory(
            id=1,
            company="Test Company",
            metric_name="revenue_growth_ttm",
            value=10.5,
            period_end="2024-03-31",
            period_type="quarterly",
            source="yahoo_finance_financials",
            created_at="2024-04-15T10:00:00Z",
        )

        assert metric.company == "Test Company"
        assert metric.metric_name == "revenue_growth_ttm"
        assert metric.value == 10.5

    def test_metric_history_defaults(self):
        metric = MetricHistory(
            company="Test Company",
            metric_name="revenue_growth_ttm",
            value=10.5,
            period_end="2024-03-31",
            period_type="quarterly",
            source="yahoo_finance_financials",
        )

        assert metric.id is None
        assert metric.created_at is None

    def test_metric_history_to_dict(self):
        metric = MetricHistory(
            id=1,
            company="Test Company",
            metric_name="revenue_growth_ttm",
            value=10.5,
            period_end="2024-03-31",
            period_type="quarterly",
            source="yahoo_finance_financials",
        )

        d = metric.to_dict()

        assert d["company"] == "Test Company"
        assert d["value"] == 10.5
        assert d["period_end"] == "2024-03-31"


class TestTriggerEvaluation:
    """Test TriggerEvaluation dataclass."""

    def test_trigger_evaluation_creation(self):
        evaluation = TriggerEvaluation(
            id=1,
            trigger_id="TRG-001",
            evaluated_at="2024-01-15T10:00:00Z",
            condition_met=True,
            current_value=3.5,
            threshold=5.0,
            details="Test evaluation",
            alert_sent=False,
            previous_status="Monitoring",
            new_status="Activated",
        )

        assert evaluation.trigger_id == "TRG-001"
        assert evaluation.condition_met is True
        assert evaluation.current_value == 3.5

    def test_trigger_evaluation_defaults(self):
        evaluation = TriggerEvaluation(
            trigger_id="TRG-001",
            evaluated_at="2024-01-15T10:00:00Z",
        )

        assert evaluation.id is None
        assert evaluation.condition_met is False
        assert evaluation.current_value is None
        assert evaluation.threshold is None
        assert evaluation.details is None
        assert evaluation.alert_sent is False
        assert evaluation.previous_status == ""
        assert evaluation.new_status == ""

    def test_trigger_evaluation_to_dict(self):
        evaluation = TriggerEvaluation(
            id=1,
            trigger_id="TRG-001",
            evaluated_at="2024-01-15T10:00:00Z",
            condition_met=True,
            current_value=3.5,
            threshold=5.0,
        )

        d = evaluation.to_dict()

        assert d["trigger_id"] == "TRG-001"
        assert d["condition_met"] is True
        assert d["current_value"] == 3.5


class TestThesisPoint:
    """Test ThesisPoint dataclass."""

    def test_thesis_point_creation(self):
        point = ThesisPoint(
            factor="Strong Revenue Growth",
            explanation="Revenue growing at 20% YoY",
            evidence="TTM revenue growth: 20%",
            additional_evidence="Quarterly growth accelerating",
            importance="High",
        )

        assert point.factor == "Strong Revenue Growth"
        assert point.importance == "High"
        assert point.additional_evidence == "Quarterly growth accelerating"

    def test_thesis_point_defaults(self):
        point = ThesisPoint(
            factor="Test Factor",
            explanation="Test explanation",
            evidence="Test evidence",
        )

        assert point.additional_evidence == ""
        assert point.importance == "Medium"

    def test_thesis_point_to_dict(self):
        point = ThesisPoint(
            factor="Test Factor",
            explanation="Test explanation",
            evidence="Test evidence",
            importance="High",
        )

        d = point.to_dict()

        assert d["factor"] == "Test Factor"
        assert d["importance"] == "High"

    def test_thesis_point_to_markdown(self):
        point = ThesisPoint(
            factor="Strong Revenue Growth",
            explanation="Revenue growing at 20% YoY",
            evidence="TTM revenue growth: 20%",
            additional_evidence="Quarterly growth accelerating",
            importance="High",
        )

        md = point.to_markdown()

        assert "**Strong Revenue Growth**" in md
        assert "Revenue growing at 20% YoY" in md
        assert "*Evidence: TTM revenue growth: 20%*" in md
        assert "*Additional: Quarterly growth accelerating*" in md


class TestThesis:
    """Test Thesis dataclass."""

    def test_thesis_creation(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[
                ThesisPoint(factor="Strong Growth", explanation="", evidence="", importance="High"),
            ],
            bear_case=[
                ThesisPoint(factor="High Valuation", explanation="", evidence="", importance="Medium"),
            ],
            base_case="Test base case",
            confidence=75,
            assumptions=["Assumption 1", "Assumption 2"],
            challenge="Key risk",
            drivers=[
                Driver("Driver 1", "Description", 8, "Positive", True, "Source"),
            ],
            competitors=["Competitor A", "Competitor B"],
        )

        assert thesis.company == "Test Company"
        assert thesis.industry == "Technology"
        assert thesis.confidence == 75
        assert len(thesis.bull_case) == 1
        assert len(thesis.bear_case) == 1
        assert len(thesis.drivers) == 1
        assert len(thesis.competitors) == 2

    def test_thesis_to_dict(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[
                ThesisPoint(factor="Strong Growth", explanation="", evidence="", importance="High"),
            ],
            bear_case=[
                ThesisPoint(factor="High Valuation", explanation="", evidence="", importance="Medium"),
            ],
            base_case="Test base case",
            confidence=75,
            assumptions=["Assumption 1"],
            challenge="Key risk",
            drivers=[
                Driver("Driver 1", "Description", 8, "Positive", True, "Source"),
            ],
            competitors=["Competitor A"],
        )

        d = thesis.to_dict()

        assert d["company"] == "Test Company"
        assert d["industry"] == "Technology"
        assert d["confidence"] == 75
        assert len(d["bull_case"]) == 1
        assert len(d["bear_case"]) == 1
        assert len(d["drivers"]) == 1
        assert len(d["competitors"]) == 1
        assert d["bull_case"][0]["factor"] == "Strong Growth"
        assert d["drivers"][0]["name"] == "Driver 1"

    def test_thesis_to_dict_empty_lists(self):
        thesis = Thesis(
            company="Test Company",
            industry="Technology",
            bull_case=[],
            bear_case=[],
            base_case="Test base case",
            confidence=75,
            assumptions=[],
            challenge="Key risk",
            drivers=[],
            competitors=[],
        )

        d = thesis.to_dict()

        assert d["bull_case"] == []
        assert d["bear_case"] == []
        assert d["drivers"] == []
        assert d["competitors"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])