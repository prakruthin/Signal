"""Tests for the notifications module."""

import pytest
import os
from unittest.mock import patch, MagicMock
from app.notifications import (
    _config,
    email_is_configured,
    _send,
    send_research_report,
    notify_trigger_changes,
    _format_trigger_condition,
    send_trigger_evaluation_alert,
)
from app.models import Trigger, TriggerCondition


class TestConfig:
    """Test configuration loading."""

    def test_config_loads(self):
        config = _config()
        assert "recipient" in config
        assert "host" in config
        assert "port" in config
        assert "username" in config
        assert "password" in config
        assert "sender" in config


class TestEmailConfigured:
    """Test email configuration check."""

    def test_email_is_configured(self):
        # Should be True with the .env configured
        result = email_is_configured()
        assert isinstance(result, bool)


class TestSendFunction:
    """Test _send function."""

    @patch("app.notifications.smtplib.SMTP")
    def test_send_success(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = _send("Test Subject", "Test Body")

        assert result == "Sent"
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @patch("app.notifications.smtplib.SMTP")
    def test_send_failure(self, mock_smtp):
        mock_smtp.side_effect = Exception("Connection refused")

        result = _send("Test Subject", "Test Body")

        assert result.startswith("Failed:")


class TestSendResearchReport:
    """Test research report email."""

    @patch("app.notifications._send")
    def test_send_research_report(self, mock_send):
        mock_send.return_value = "Sent"

        triggers = [
            Trigger("TRG-001", "Negative", "Test trigger 1", 80, "High", "Driver 1", "Company", "Industry", "Daily"),
            Trigger("TRG-002", "Positive", "Test trigger 2", 75, "Medium", "Driver 2", "Company", "Industry", "Weekly"),
        ]

        result = send_research_report(
            company="Test Company",
            summary="Test thesis summary",
            profile={"Ticker": "TEST.NS", "Price": "100"},
            triggers=triggers,
        )

        assert result == "Sent"
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert "Test Company" in args[0]  # Subject
        assert "Test thesis summary" in args[1]  # Body
        assert "TRG-001" in args[1]
        assert "TRG-002" in args[1]


class TestFormatTriggerCondition:
    """Test trigger condition formatting for emails."""

    def test_format_financial_metric(self):
        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Negative",
            description="Test",
            confidence=80,
            importance="High",
            related_driver="Revenue growth",
            related_companies="Test Company",
            related_industry="Technology",
            monitoring_frequency="Weekly",
            condition={
                "condition_type": "financial_metric",
                "metric_name": "revenue_growth_ttm",
                "operator": "<",
                "threshold": 5.0,
                "unit": "percent",
                "lookback_periods": 2,
                "period_type": "quarterly",
                "consecutive": True,
                "allow_gaps": True,
            },
        )

        formatted = _format_trigger_condition(trigger)

        assert "Type: Financial Metric" in formatted
        assert "revenue_growth_ttm" in formatted
        assert "<" in formatted
        assert "5.0" in formatted
        assert "percent" in formatted
        assert "2 quarterly" in formatted
        assert "Consecutive: True" in formatted

    def test_format_news_keyword(self):
        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Positive",
            description="Test",
            confidence=75,
            importance="High",
            related_driver="Regulatory risk",
            related_companies="Test Company",
            related_industry="Technology",
            monitoring_frequency="Daily",
            condition={
                "condition_type": "news_keyword",
                "keywords": ["bankruptcy", "default"],
                "lookback_periods": 7,
                "threshold": 1,
            },
        )

        formatted = _format_trigger_condition(trigger)

        assert "Type: News Keyword" in formatted
        assert "bankruptcy, default" in formatted
        assert "7 days" in formatted
        assert "1 matching headlines" in formatted

    def test_format_news_sentiment(self):
        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Positive",
            description="Test",
            confidence=70,
            importance="Medium",
            related_driver="Sentiment spike",
            related_companies="Test Company",
            related_industry="Technology",
            monitoring_frequency="Daily",
            condition={
                "condition_type": "news_sentiment",
                "sentiment_threshold": -0.3,
                "lookback_periods": 7,
                "threshold": 3,
            },
        )

        formatted = _format_trigger_condition(trigger)

        assert "Type: News Sentiment" in formatted
        assert "-0.3" in formatted
        assert "7 days" in formatted
        assert "3 headlines" in formatted

    def test_format_news_volume(self):
        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Hold",
            description="Test",
            confidence=65,
            importance="Medium",
            related_driver="News volume",
            related_companies="Test Company",
            related_industry="Technology",
            monitoring_frequency="Daily",
            condition={
                "condition_type": "news_volume",
                "volume_multiplier": 2.0,
                "lookback_periods": 30,
                "threshold": 5,
            },
        )

        formatted = _format_trigger_condition(trigger)

        assert "Type: News Volume Spike" in formatted
        assert "2.0x" in formatted
        assert "30 days" in formatted
        assert "5" in formatted

    def test_format_price_change(self):
        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Negative",
            description="Test",
            confidence=80,
            importance="High",
            related_driver="Price drop",
            related_companies="Test Company",
            related_industry="Technology",
            monitoring_frequency="Hours",
            condition={
                "condition_type": "price_change",
                "metric_name": "price_change_pct",
                "operator": "<",
                "threshold": -5.0,
                "lookback_periods": 1,
            },
        )

        formatted = _format_trigger_condition(trigger)

        assert "Type: Price Change" in formatted
        assert "price_change_pct" in formatted
        assert "<" in formatted
        assert "-5.0%" in formatted

    def test_format_no_condition(self):
        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Negative",
            description="Test",
            confidence=80,
            importance="High",
            related_driver="Test",
            related_companies="Test Company",
            related_industry="Technology",
            monitoring_frequency="Daily",
            condition=None,
        )

        formatted = _format_trigger_condition(trigger)
        assert "No structured condition defined" in formatted


class TestNotifyTriggerChanges:
    """Test trigger change notifications."""

    @patch("app.notifications._send")
    @patch("app.notifications.alert_was_sent")
    @patch("app.notifications.record_alert")
    @patch("app.notifications.set_trigger_status")
    @patch("app.notifications.trigger_status")
    def test_notify_trigger_changes_status_changed(self, mock_trigger_status, mock_set_status, mock_record_alert, mock_alert_was_sent, mock_send):
        mock_trigger_status.return_value = None
        mock_alert_was_sent.return_value = False
        mock_send.return_value = "Sent"

        triggers = [
            Trigger("TRG-001", "Negative", "Test trigger", 80, "High", "Driver 1", "Test Company", "Technology", "Daily", status="Activated"),
        ]

        result = notify_trigger_changes(
            company="Test Company",
            before={"TRG-001": "Monitoring"},
            triggers=triggers,
            event="Test event",
            assessment={"outcome": "Test", "impact": "Negative", "confidence": 80, "recommendation": "Review"},
        )

        assert len(result) == 1
        assert "TRG-001" in result[0]
        assert "Sent" in result[0]
        mock_send.assert_called_once()
        mock_record_alert.assert_called_once()
        mock_set_status.assert_called_once()

    @patch("app.notifications.trigger_status")
    def test_notify_trigger_changes_no_change(self, mock_trigger_status):
        mock_trigger_status.return_value = "Monitoring"

        triggers = [
            Trigger("TRG-001", "Negative", "Test trigger", 80, "High", "Driver 1", "Test Company", "Technology", "Daily", status="Monitoring"),
        ]

        result = notify_trigger_changes(
            company="Test Company",
            before={"TRG-001": "Monitoring"},
            triggers=triggers,
            event="Test event",
            assessment={"outcome": "Test", "impact": "Negative", "confidence": 80, "recommendation": "Review"},
        )

        # Should return empty list or list with "already sent"/"no email required"
        assert isinstance(result, list)

    @patch("app.notifications.alert_was_sent")
    @patch("app.notifications.trigger_status")
    def test_notify_trigger_changes_duplicate_prevented(self, mock_trigger_status, mock_alert_was_sent):
        mock_trigger_status.return_value = None
        mock_alert_was_sent.return_value = True

        triggers = [
            Trigger("TRG-001", "Negative", "Test trigger", 80, "High", "Driver 1", "Test Company", "Technology", "Daily", status="Activated"),
        ]

        result = notify_trigger_changes(
            company="Test Company",
            before={"TRG-001": "Monitoring"},
            triggers=triggers,
            event="Test event",
            assessment={"outcome": "Test", "impact": "Negative", "confidence": 80, "recommendation": "Review"},
        )

        assert len(result) == 1
        assert "already sent" in result[0]


class TestSendTriggerEvaluationAlert:
    """Test automated trigger evaluation alert."""

    @patch("app.notifications._send")
    def test_send_trigger_evaluation_alert(self, mock_send):
        mock_send.return_value = "Sent"

        trigger = Trigger(
            trigger_id="TRG-TEST",
            category="Negative",
            description="Operating margin below threshold",
            confidence=85,
            importance="Critical",
            related_driver="Operating profitability",
            related_companies="Test Company",
            related_industry="Technology",
            monitoring_frequency="Daily",
            condition={
                "condition_type": "financial_metric",
                "metric_name": "operating_margin_ttm",
                "operator": "<",
                "threshold": -5.0,
                "unit": "percent",
            },
        )

        result = send_trigger_evaluation_alert(
            company="Test Company",
            trigger=trigger,
            evaluation={
                "condition_met": True,
                "current_value": -6.93,
                "threshold": -5.0,
                "details": "Latest value: -6.93, condition < -5.0 met",
                "evaluated_at": "2024-01-15T10:00:00Z",
            },
            old_status="Monitoring",
            new_status="Activated",
        )

        assert result == "Sent"
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert "Activated" in args[0]
        assert "Test Company" in args[0]
        assert "TRG-TEST" in args[0]
        assert "Operating margin" in args[1]
        assert "-6.93" in args[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])