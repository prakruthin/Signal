"""Tests for the store module."""

import pytest
import os
from app.store import (
    save_thesis,
    thesis_history,
    alert_was_sent,
    record_alert,
    trigger_status,
    set_trigger_status,
    save_trigger_condition,
    get_trigger_condition,
    get_all_trigger_conditions,
    get_all_companies_with_triggers,
    get_all_trigger_states,
    store_metric_history,
    get_metric_history,
    log_trigger_evaluation,
    get_trigger_evaluations,
    _normalize_company,
)
from app.models import TriggerCondition


class TestNormalizeCompany:
    """Test company name normalization."""

    def test_normalize_company(self):
        assert _normalize_company("  Vodafone Idea  ") == "Vodafone Idea"
        assert _normalize_company("Vodafone Idea") == "Vodafone Idea"
        assert _normalize_company("") == ""
        assert _normalize_company(None) is None


class TestThesisStorage:
    """Test thesis version storage."""

    def test_save_thesis_new_company(self):
        # Use unique company name to avoid conflicts
        import uuid
        company = f"Test Company New {uuid.uuid4().hex[:8]}"
        version = save_thesis(company, "Test thesis summary", "Test reason")
        assert version == 1

    def test_save_thesis_existing_company(self):
        import uuid
        company = f"Test Company New 2 {uuid.uuid4().hex[:8]}"
        save_thesis(company, "Version 1", "Initial")
        version = save_thesis(company, "Version 2", "Update")
        assert version == 2

    def test_thesis_history(self):
        import uuid
        company = f"History Test Company {uuid.uuid4().hex[:8]}"
        save_thesis(company, "V1", "Initial")
        save_thesis(company, "V2", "Update")

        history = thesis_history(company)

        assert len(history) == 2
        assert history[0][0] == "v2"
        assert history[1][0] == "v1"
        assert history[0][1] == "Update"
        assert history[1][1] == "Initial"


class TestAlertDeduplication:
    """Test alert deduplication."""

    def test_alert_was_sent_new(self):
        import uuid
        # Clean fingerprint
        fingerprint = f"test|company|trigger|status|event|{uuid.uuid4().hex[:8]}"
        # Should not exist
        assert alert_was_sent(fingerprint) is False

    def test_record_alert(self):
        import uuid
        fingerprint = f"test_record|company|trigger|status|event|{uuid.uuid4().hex[:8]}"
        record_alert(fingerprint, "Test Company", "TRG-TEST", "Activated", "Sent", "Test Subject")
        assert alert_was_sent(fingerprint) is True

    def test_record_alert_duplicate(self):
        import uuid
        from sqlalchemy.exc import IntegrityError
        fingerprint = f"test_dup|company|trigger|status|event|{uuid.uuid4().hex[:8]}"
        record_alert(fingerprint, "Test Company", "TRG-TEST", "Activated", "Sent", "Test Subject")
        # Second call should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            record_alert(fingerprint, "Test Company", "TRG-TEST", "Activated", "Sent", "Test Subject")


class TestTriggerState:
    """Test trigger state management."""

    def test_trigger_status_new(self):
        status = trigger_status("New Company Triggers", "TRG-NEW")
        assert status is None

    def test_set_and_get_trigger_status(self):
        company = "Trigger State Test Company"
        trigger_id = "TRG-TEST-STATUS"

        # Set status
        set_trigger_status(company, trigger_id, "Activated")

        # Get status
        status = trigger_status(company, trigger_id)
        assert status == "Activated"

    def test_update_trigger_status(self):
        company = "Trigger Update Test"
        trigger_id = "TRG-UPDATE"

        set_trigger_status(company, trigger_id, "Monitoring")
        assert trigger_status(company, trigger_id) == "Monitoring"

        set_trigger_status(company, trigger_id, "Strengthened")
        assert trigger_status(company, trigger_id) == "Strengthened"


class TestTriggerConditionStorage:
    """Test trigger condition storage."""

    def test_save_and_get_trigger_condition(self):
        trigger_id = "TRG-CONDITION-TEST"
        condition = {
            "condition_type": "financial_metric",
            "metric_name": "revenue_growth_ttm",
            "operator": "<",
            "threshold": 5.0,
            "unit": "percent",
            "lookback_periods": 2,
            "period_type": "quarterly",
            "consecutive": True,
            "allow_gaps": True,
            "keywords": None,
            "sentiment_threshold": None,
            "volume_multiplier": None,
            "data_source": "yahoo_finance_financials",
            "description": "Test trigger condition",
            "category": "Negative",
            "confidence": 85,
            "importance": "Critical",
            "related_driver": "Revenue growth",
            "monitoring_frequency": "Weekly",
            "status": "Monitoring",
        }

        save_trigger_condition(trigger_id, condition)
        retrieved = get_trigger_condition(trigger_id)

        assert retrieved["trigger_id"] == trigger_id
        assert retrieved["condition_type"] == "financial_metric"
        assert retrieved["metric_name"] == "revenue_growth_ttm"
        assert retrieved["threshold"] == 5.0
        assert retrieved["category"] == "Negative"
        assert retrieved["confidence"] == 85

    def test_save_trigger_condition_news_keyword(self):
        trigger_id = "TRG-NEWS-TEST"
        condition = {
            "condition_type": "news_keyword",
            "keywords": ["bankruptcy", "default", "liquidation"],
            "lookback_periods": 7,
            "threshold": 1,
            "unit": "count",
            "data_source": "google_news_rss",
            "description": "News keyword trigger",
            "category": "Positive",
            "confidence": 75,
            "importance": "High",
            "related_driver": "Regulatory risk",
            "monitoring_frequency": "Daily",
            "status": "Monitoring",
        }

        save_trigger_condition(trigger_id, condition)
        retrieved = get_trigger_condition(trigger_id)

        assert retrieved["condition_type"] == "news_keyword"
        assert retrieved["keywords"] == ["bankruptcy", "default", "liquidation"]
        assert retrieved["lookback_periods"] == 7

    def test_get_all_trigger_conditions(self):
        company = "All Conditions Test Company"
        trigger_ids = ["TRG-ALL-1", "TRG-ALL-2"]

        for tid in trigger_ids:
            set_trigger_status(company, tid, "Monitoring")
            save_trigger_condition(tid, {
                "condition_type": "financial_metric",
                "metric_name": "revenue_growth_ttm",
                "operator": "<",
                "threshold": 5.0,
                "unit": "percent",
                "lookback_periods": 1,
                "period_type": "quarterly",
                "consecutive": False,
                "allow_gaps": True,
                "data_source": "yahoo_finance_financials",
                "description": f"Test {tid}",
                "category": "Negative",
                "confidence": 80,
                "importance": "High",
                "related_driver": "Revenue growth",
                "monitoring_frequency": "Daily",
                "status": "Monitoring",
            })

        conditions = get_all_trigger_conditions(company)

        assert len(conditions) == 2
        retrieved_ids = {c["trigger_id"] for c in conditions}
        assert retrieved_ids == set(trigger_ids)

    def test_get_all_companies_with_triggers(self):
        companies = get_all_companies_with_triggers()
        assert isinstance(companies, list)
        # Should have at least the companies we created in other tests
        assert len(companies) >= 1

    def test_get_all_trigger_states(self):
        states = get_all_trigger_states()
        assert isinstance(states, list)
        for state in states:
            assert "company" in state
            assert "trigger_id" in state
            assert "status" in state


class TestMetricHistory:
    """Test metric history storage."""

    def test_store_and_get_metric_history(self):
        company = "Metric History Test Company"
        metric_name = "revenue_growth_ttm"

        # Store some values
        store_metric_history(company, metric_name, 10.5, "2024-03-31", "quarterly", "yahoo_finance_financials")
        store_metric_history(company, metric_name, 8.2, "2023-12-31", "quarterly", "yahoo_finance_financials")
        store_metric_history(company, metric_name, 9.1, "2023-09-30", "quarterly", "yahoo_finance_financials")

        # Retrieve
        history = get_metric_history(company, metric_name, limit=5)

        assert len(history) == 3
        assert history[0]["value"] == 10.5
        assert history[0]["period_end"] == "2024-03-31"
        assert history[1]["value"] == 8.2
        assert history[2]["value"] == 9.1


class TestTriggerEvaluation:
    """Test trigger evaluation logging."""

    def test_log_and_get_trigger_evaluation(self):
        import uuid
        trigger_id = f"TRG-EVAL-TEST-{uuid.uuid4().hex[:8]}"

        evaluation = {
            "trigger_id": trigger_id,
            "evaluated_at": "2024-01-15T10:00:00Z",
            "condition_met": True,
            "current_value": 3.5,
            "threshold": 5.0,
            "details": "Test evaluation",
            "alert_sent": False,
            "previous_status": "Monitoring",
            "new_status": "Activated",
        }

        log_trigger_evaluation(evaluation)
        evaluations = get_trigger_evaluations(trigger_id, limit=10)

        assert len(evaluations) >= 1
        latest = evaluations[0]
        assert latest["condition_met"] is True
        assert latest["current_value"] == 3.5
        assert latest["new_status"] == "Activated"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])