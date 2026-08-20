"""Tests for the trigger evaluation engine."""

import pytest
from datetime import datetime, timezone
from app.trigger_evaluator import TriggerEvaluator
from app.trigger_conditions import (
    parse_condition,
    validate_condition,
    evaluate_financial_condition,
    evaluate_news_keyword_condition,
    evaluate_news_sentiment_condition,
    evaluate_news_volume_condition,
    evaluate_price_condition,
    get_required_data_source,
    frequency_to_scheduler_args,
    condition_to_dict,
    dict_to_condition,
)
from app.models import Trigger, TriggerCondition, TriggerEvaluation


class TestConditionParsing:
    """Test condition parsing and validation."""

    def test_parse_financial_metric_condition(self):
        condition_dict = {
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

        condition = parse_condition(condition_dict)

        assert isinstance(condition, TriggerCondition)
        assert condition.condition_type == "financial_metric"
        assert condition.metric_name == "revenue_growth_ttm"
        assert condition.operator == "<"
        assert condition.threshold == 5.0
        assert condition.unit == "percent"
        assert condition.lookback_periods == 2
        assert condition.period_type == "quarterly"
        assert condition.consecutive is True
        assert condition.allow_gaps is True
        assert condition.data_source == "yahoo_finance_financials"

    def test_parse_news_keyword_condition(self):
        condition_dict = {
            "condition_type": "news_keyword",
            "keywords": ["bankruptcy", "default", "liquidation"],
            "lookback_periods": 7,
            "threshold": 1,
            "data_source": "google_news_rss",
        }

        condition = parse_condition(condition_dict)

        assert condition.condition_type == "news_keyword"
        assert condition.keywords == ["bankruptcy", "default", "liquidation"]
        assert condition.lookback_periods == 7
        assert condition.threshold == 1
        assert condition.unit == "count"

    def test_parse_news_sentiment_condition(self):
        condition_dict = {
            "condition_type": "news_sentiment",
            "sentiment_threshold": -0.3,
            "lookback_periods": 7,
            "threshold": 3,
            "data_source": "google_news_rss",
        }

        condition = parse_condition(condition_dict)

        assert condition.condition_type == "news_sentiment"
        assert condition.sentiment_threshold == -0.3
        assert condition.lookback_periods == 7
        assert condition.threshold == 3

    def test_parse_news_volume_condition(self):
        condition_dict = {
            "condition_type": "news_volume",
            "volume_multiplier": 2.0,
            "lookback_periods": 30,
            "threshold": 5,
            "data_source": "google_news_rss",
        }

        condition = parse_condition(condition_dict)

        assert condition.condition_type == "news_volume"
        assert condition.volume_multiplier == 2.0
        assert condition.lookback_periods == 30
        assert condition.threshold == 5

    def test_parse_price_change_condition(self):
        condition_dict = {
            "condition_type": "price_change",
            "metric_name": "price_change_pct",
            "operator": ">",
            "threshold": 5.0,
            "unit": "percent",
            "lookback_periods": 1,
            "data_source": "yahoo_finance_price",
        }

        condition = parse_condition(condition_dict)

        assert condition.condition_type == "price_change"
        assert condition.metric_name == "price_change_pct"
        assert condition.operator == ">"
        assert condition.threshold == 5.0

    def test_parse_unknown_condition_type(self):
        condition_dict = {"condition_type": "unknown_type"}

        with pytest.raises(ValueError, match="Unknown condition_type"):
            parse_condition(condition_dict)


class TestConditionValidation:
    """Test condition validation."""

    def test_validate_financial_metric_valid(self):
        condition = TriggerCondition(
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

        errors = validate_condition(condition)
        assert errors == []

    def test_validate_financial_metric_missing_metric(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            operator="<",
            threshold=5.0,
        )

        errors = validate_condition(condition)
        assert "financial_metric requires metric_name" in errors

    def test_validate_financial_metric_invalid_metric(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            metric_name="invalid_metric",
            operator="<",
            threshold=5.0,
        )

        errors = validate_condition(condition)
        assert "Unknown financial metric" in errors[0]

    def test_validate_financial_metric_invalid_operator(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            metric_name="revenue_growth_ttm",
            operator="invalid",
            threshold=5.0,
        )

        errors = validate_condition(condition)
        assert "Invalid operator" in errors[0]

    def test_validate_news_keyword_missing_keywords(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_keyword",
        )

        errors = validate_condition(condition)
        assert "news_keyword requires keywords list" in errors

    def test_validate_news_sentiment_invalid_threshold(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_sentiment",
            sentiment_threshold=1.5,
        )

        errors = validate_condition(condition)
        assert "sentiment_threshold must be between -1 and 1" in errors

    def test_validate_news_volume_invalid_multiplier(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_volume",
            volume_multiplier=0.5,
        )

        errors = validate_condition(condition)
        assert "volume_multiplier > 1" in errors[0]


class TestFinancialConditionEvaluation:
    """Test financial condition evaluation."""

    def test_evaluate_financial_condition_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            metric_name="revenue_growth_ttm",
            operator="<",
            threshold=5.0,
            lookback_periods=1,
            consecutive=False,
        )

        met, details = evaluate_financial_condition(condition, [3.0], 3.0)
        assert met is True
        assert "met" in details.lower()

    def test_evaluate_financial_condition_not_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            metric_name="revenue_growth_ttm",
            operator="<",
            threshold=5.0,
            lookback_periods=1,
            consecutive=False,
        )

        met, details = evaluate_financial_condition(condition, [10.0], 10.0)
        assert met is False
        assert "not met" in details.lower()

    def test_evaluate_financial_condition_consecutive_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            metric_name="revenue_growth_ttm",
            operator="<",
            threshold=5.0,
            lookback_periods=3,
            consecutive=True,
        )

        met, details = evaluate_financial_condition(condition, [3.0, 4.0, 2.0], 3.0)
        assert met is True
        assert "3 periods" in details

    def test_evaluate_financial_condition_consecutive_not_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            metric_name="revenue_growth_ttm",
            operator="<",
            threshold=5.0,
            lookback_periods=3,
            consecutive=True,
        )

        met, details = evaluate_financial_condition(condition, [3.0, 6.0, 2.0], 3.0)
        assert met is False

    def test_evaluate_financial_condition_insufficient_data(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            metric_name="revenue_growth_ttm",
            operator="<",
            threshold=5.0,
            lookback_periods=3,
            consecutive=True,
        )

        met, details = evaluate_financial_condition(condition, [3.0], 3.0)
        assert met is False
        assert "Need 3 periods" in details


class TestNewsKeywordConditionEvaluation:
    """Test news keyword condition evaluation."""

    def test_evaluate_news_keyword_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_keyword",
            keywords=["bankruptcy", "default"],
            lookback_periods=7,
            threshold=1,
        )

        headlines = [
            {"finding": "Company faces bankruptcy risk", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
            {"finding": "Market rally continues", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
        ]

        met, details = evaluate_news_keyword_condition(condition, headlines, 7)
        assert met is True
        assert "1 matching" in details

    def test_evaluate_news_keyword_not_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_keyword",
            keywords=["bankruptcy", "default"],
            lookback_periods=7,
            threshold=2,
        )

        headlines = [
            {"finding": "Company faces bankruptcy risk", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
        ]

        met, details = evaluate_news_keyword_condition(condition, headlines, 7)
        assert met is False
        assert "1 matching" in details

    def test_evaluate_news_keyword_empty(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_keyword",
            keywords=[],
            lookback_periods=7,
            threshold=1,
        )

        met, details = evaluate_news_keyword_condition(condition, [], 7)
        assert met is False
        assert "No keywords" in details


class TestNewsSentimentConditionEvaluation:
    """Test news sentiment condition evaluation."""

    def test_evaluate_news_sentiment_negative_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_sentiment",
            sentiment_threshold=-0.3,
            lookback_periods=7,
            threshold=3,
        )

        headlines = [
            {"finding": "Loss reported", "impact": "Negative", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
            {"finding": "Debt increases", "impact": "Negative", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
            {"finding": "Probe launched", "impact": "Negative", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
            {"finding": "Profit rises", "impact": "Positive", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
        ]

        met, details = evaluate_news_sentiment_condition(condition, headlines, 7)
        assert met is True
        assert "3 headlines" in details

    def test_evaluate_news_sentiment_positive_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_sentiment",
            sentiment_threshold=0.3,
            lookback_periods=7,
            threshold=2,
        )

        headlines = [
            {"finding": "Profit beats", "impact": "Positive", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
            {"finding": "Growth strong", "impact": "Positive", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
        ]

        met, details = evaluate_news_sentiment_condition(condition, headlines, 7)
        assert met is True


class TestNewsVolumeConditionEvaluation:
    """Test news volume spike condition evaluation."""

    def test_evaluate_news_volume_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_volume",
            volume_multiplier=2.0,
            lookback_periods=30,
            threshold=5,
        )

        # Create headlines with proper dates
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        headlines = []
        for i in range(10):
            h_date = now - timedelta(days=i)
            headlines.append({"finding": f"Headline {i}", "observed_at": h_date.strftime("%Y-%m-%d %H:%M:%S UTC")})
        for i in range(10):
            h_date = now - timedelta(days=40 + i)
            headlines.append({"finding": f"Old headline {i}", "observed_at": h_date.strftime("%Y-%m-%d %H:%M:%S UTC")})

        met, details = evaluate_news_volume_condition(condition, headlines, 7)
        assert met is True

    def test_evaluate_news_volume_not_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="news_volume",
            volume_multiplier=2.0,
            lookback_periods=30,
            threshold=5,
        )

        # Only 2 headlines in recent period
        headlines = [
            {"finding": "Headline 1", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
            {"finding": "Headline 2", "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
        ]

        met, details = evaluate_news_volume_condition(condition, headlines, 7)
        assert met is False


class TestPriceConditionEvaluation:
    """Test price change condition evaluation."""

    def test_evaluate_price_condition_met_positive(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="price_change",
            metric_name="price_change_pct",
            operator=">",
            threshold=5.0,
        )

        # 105 vs 100 = 5% change, which is NOT > 5%, it's == 5%
        # Use 106 to get 6% change
        met, details = evaluate_price_condition(condition, 106.0, 100.0)
        assert met is True
        assert "6.00%" in details

    def test_evaluate_price_condition_not_met(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="price_change",
            metric_name="price_change_pct",
            operator=">",
            threshold=5.0,
        )

        met, details = evaluate_price_condition(condition, 102.0, 100.0)
        assert met is False
        assert "2.00%" in details

    def test_evaluate_price_condition_zero_previous(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="price_change",
            metric_name="price_change_pct",
            operator=">",
            threshold=5.0,
        )

        met, details = evaluate_price_condition(condition, 100.0, 0.0)
        assert met is False
        assert "Previous price is zero" in details


class TestDataSourceAndScheduler:
    """Test data source mapping and scheduler args."""

    def test_get_required_data_source(self):
        condition = TriggerCondition(
            trigger_id="TRG-TEST",
            condition_type="financial_metric",
            data_source="yahoo_finance_financials",
        )
        assert get_required_data_source(condition) == "yahoo_finance_financials"

        condition.data_source = "google_news_rss"
        assert get_required_data_source(condition) == "google_news_rss"

    def test_frequency_to_scheduler_args(self):
        assert frequency_to_scheduler_args("Hours") == {"trigger": "interval", "hours": 1}
        assert frequency_to_scheduler_args("Daily") == {"trigger": "cron", "hour": 6, "minute": 0}
        assert frequency_to_scheduler_args("Weekly") == {"trigger": "cron", "day_of_week": "mon", "hour": 6, "minute": 0}
        assert frequency_to_scheduler_args("Monthly") == {"trigger": "cron", "day": 1, "hour": 6, "minute": 0}
        assert frequency_to_scheduler_args("Unknown") == {"trigger": "interval", "hours": 1}


class TestConditionSerialization:
    """Test condition serialization."""

    def test_condition_to_dict(self):
        condition = TriggerCondition(
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

        d = condition_to_dict(condition)

        assert d["trigger_id"] == "TRG-TEST"
        assert d["condition_type"] == "financial_metric"
        assert d["metric_name"] == "revenue_growth_ttm"
        assert d["threshold"] == 5.0

    def test_dict_to_condition(self):
        data = {
            "trigger_id": "TRG-TEST",
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

        condition = dict_to_condition(data)

        assert condition.trigger_id == "TRG-TEST"
        assert condition.condition_type == "financial_metric"
        assert condition.metric_name == "revenue_growth_ttm"
        assert condition.threshold == 5.0


class TestTriggerEvaluator:
    """Test TriggerEvaluator class."""

    def test_evaluator_initialization(self):
        evaluator = TriggerEvaluator()
        assert evaluator.yahoo_fetcher is not None
        assert evaluator.rss_fetcher is not None

    def test_evaluate_trigger_no_condition(self):
        evaluator = TriggerEvaluator()
        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Negative",
            description="Test",
            confidence=80,
            importance="High",
            related_driver="Test",
            related_companies="Test",
            related_industry="Test",
            monitoring_frequency="Daily",
            status="Monitoring",
            condition=None,
        )

        result = evaluator.evaluate_trigger(trigger, "Test Company", "TEST.NS", [], "Test Industry")

        assert result.condition_met is False
        assert "No condition defined" in result.details

    def test_evaluate_trigger_invalid_condition(self):
        evaluator = TriggerEvaluator()
        # Use a condition that passes parse_condition but fails validation
        # Missing required metric_name for financial_metric
        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Negative",
            description="Test",
            confidence=80,
            importance="High",
            related_driver="Test",
            related_companies="Test",
            related_industry="Test",
            monitoring_frequency="Daily",
            status="Monitoring",
            condition={"condition_type": "financial_metric"},  # Missing metric_name
        )

        result = evaluator.evaluate_trigger(trigger, "Test Company", "TEST.NS", [], "Test Industry")

        assert result.condition_met is False
        assert "Invalid condition" in result.details or "requires metric_name" in result.details


if __name__ == "__main__":
    pytest.main([__file__, "-v"])