"""Email notifications for material trigger state changes."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Dict, List, Optional

from dotenv import load_dotenv

from .models import Trigger
from .store import alert_was_sent, record_alert, set_trigger_status, trigger_status

load_dotenv()

###
# try:
#     with smtplib.SMTP("smtp.office365.com", 587, timeout=20) as s:
#         s.set_debuglevel(1)  # prints the raw SMTP conversation
#         s.ehlo()
#         s.starttls()
#         s.ehlo()
#         print("Handshake OK")
# except Exception as e:
#     print("Failed:", type(e).__name__, e)
### End of test

def _config() -> Dict[str, str]:
    return {
        "recipient": os.getenv("ALERT_RECIPIENT", "").strip(),
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": os.getenv("SMTP_PORT", "587").strip(),
        "username": os.getenv("SMTP_USERNAME", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip('"'),
        "sender": os.getenv("ALERT_FROM", os.getenv("SMTP_USERNAME", "")).strip(),
    }


def email_is_configured() -> bool:
    c = _config()
    return bool(c["recipient"] and c["host"] and c["sender"])


def _send(subject: str, body: str) -> str:
    c = _config()
    if not email_is_configured():
        return "Not configured"
    message = EmailMessage()
    message["From"] = c["sender"]
    message["To"] = c["recipient"]
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(c["host"], int(c["port"]), timeout=20) as smtp:
            smtp.starttls()
            if c["username"]:
                smtp.login(c["username"], c["password"])
            smtp.send_message(message)
        return "Sent"
    except Exception as exc:
        return f"Failed: {type(exc).__name__}: {exc}"


def send_research_report(
    company: str,
    summary: str,
    profile: dict,
    triggers: list,
) -> str:
    """Send completed investment research report."""

    if not email_is_configured():
        return "Email not configured"

    profile_text = "\n".join(
        f"{key}: {value}"
        for key, value in profile.items()
    )

    trigger_text = "\n".join(
        f"- {trigger.trigger_id}: {trigger.description}"
        for trigger in triggers
    )

    subject = f"Investment Research Completed — {company}"

    body = (
        f"Investment Intelligence Report\n\n"
        f"Company: {company}\n\n"
        f"====================\n"
        f"INVESTMENT THESIS\n"
        f"====================\n\n"
        f"{summary}\n\n"
        f"====================\n"
        f"COMPANY PROFILE\n"
        f"====================\n\n"
        f"{profile_text}\n\n"
        f"====================\n"
        f"MONITORED TRIGGERS\n"
        f"====================\n\n"
        f"{trigger_text}\n\n"
        f"Decision support only — verify primary sources before acting."
        
    )
    report_sent = _send(subject, body)

    return report_sent


def _format_trigger_condition(trigger: Trigger) -> str:
    """Format trigger condition details for email."""
    if not trigger.condition:
        return "No structured condition defined"
    
    cond = trigger.condition
    ct = cond.get("condition_type", "")
    
    if ct == "financial_metric":
        return (
            f"Type: Financial Metric\n"
            f"Metric: {cond.get('metric_name', 'N/A')}\n"
            f"Condition: {cond.get('metric_name')} {cond.get('operator')} {cond.get('threshold')} {cond.get('unit')}\n"
            f"Lookback: {cond.get('lookback_periods')} {cond.get('period_type')}(s)\n"
            f"Consecutive: {cond.get('consecutive', False)}\n"
            f"Allow gaps: {cond.get('allow_gaps', True)}"
        )
    elif ct == "news_keyword":
        return (
            f"Type: News Keyword\n"
            f"Keywords: {', '.join(cond.get('keywords', []))}\n"
            f"Lookback: {cond.get('lookback_periods')} days\n"
            f"Threshold: {cond.get('threshold')} matching headlines"
        )
    elif ct == "news_sentiment":
        return (
            f"Type: News Sentiment\n"
            f"Sentiment threshold: {cond.get('sentiment_threshold')}\n"
            f"Lookback: {cond.get('lookback_periods')} days\n"
            f"Threshold: {cond.get('threshold')} headlines beyond threshold"
        )
    elif ct == "news_volume":
        return (
            f"Type: News Volume Spike\n"
            f"Volume multiplier: {cond.get('volume_multiplier')}x baseline\n"
            f"Baseline window: {cond.get('lookback_periods')} days\n"
            f"Minimum headlines: {cond.get('threshold')}"
        )
    elif ct == "price_change":
        return (
            f"Type: Price Change\n"
            f"Metric: {cond.get('metric_name', 'price_change_pct')}\n"
            f"Condition: {cond.get('operator')} {cond.get('threshold')}%\n"
            f"Lookback: {cond.get('lookback_periods')} period(s)"
        )
    return f"Unknown condition type: {ct}"


def notify_trigger_changes(company: str, before: Dict[str, str], triggers: List[Trigger], event: str, assessment: Dict) -> List[str]:
    """Send one alert per changed trigger, avoiding duplicate delivery for the same event/state."""
    outcomes = []
    for trigger in triggers:
        old_status = trigger_status(company, trigger.trigger_id) or before.get(trigger.trigger_id, "Monitoring")
        if trigger.status == old_status:
            set_trigger_status(company, trigger.trigger_id, trigger.status)
            continue
        fingerprint = f"{company}|{trigger.trigger_id}|{old_status}|{trigger.status}|{event[:160]}"
        if alert_was_sent(fingerprint):
            outcomes.append(f"{trigger.trigger_id}: already sent")
            continue
        
        subject = f"{trigger.status} — {company} — {trigger.trigger_id}"
        
        condition_details = _format_trigger_condition(trigger)
        
        body = (
            f"Trigger Alert — {trigger.status}\n\n"
            f"Company: {company}\n"
            f"Trigger ID: {trigger.trigger_id}\n"
            f"Category: {trigger.category}\n"
            f"Importance: {trigger.importance}\n"
            f"Monitoring Frequency: {trigger.monitoring_frequency}\n"
            f"Status Change: {old_status} → {trigger.status}\n\n"
            f"=== Trigger Description ===\n"
            f"{trigger.description}\n\n"
            f"=== Related Driver ===\n"
            f"{trigger.related_driver}\n\n"
            f"=== Condition Details ===\n"
            f"{condition_details}\n\n"
            f"=== Evaluation Details ===\n"
            f"Event/Evidence: {event}\n"
            f"Analyst Assessment: {assessment.get('outcome', 'N/A')} ({assessment.get('impact', 'Unclear')})\n"
            f"Confidence: {assessment.get('confidence', 'N/A')}/100\n"
            f"Recommendation: {assessment.get('recommendation', 'Review the evidence.')}\n\n"
            f"=== Source Information ===\n"
            f"Related Companies: {trigger.related_companies}\n"
            f"Industry: {trigger.related_industry}\n\n"
            f"Decision support only — verify primary sources before acting."
        )
        
        delivery = _send(subject, body)
        record_alert(fingerprint, company, trigger.trigger_id, trigger.status, delivery, subject)
        set_trigger_status(company, trigger.trigger_id, trigger.status)
        outcomes.append(f"{trigger.trigger_id}: {delivery}")
    return outcomes


def send_trigger_evaluation_alert(
    company: str,
    trigger: Trigger,
    evaluation: Dict,
    old_status: str,
    new_status: str
) -> str:
    """Send detailed alert for automated trigger evaluation (from trigger_monitor)."""
    if not email_is_configured():
        return "Email not configured"
    
    subject = f"{new_status} — {company} — {trigger.trigger_id}"
    
    condition_details = _format_trigger_condition(trigger)
    
    body = (
        f"Automated Trigger Evaluation — {new_status}\n\n"
        f"Company: {company}\n"
        f"Trigger ID: {trigger.trigger_id}\n"
        f"Category: {trigger.category}\n"
        f"Importance: {trigger.importance}\n"
        f"Monitoring Frequency: {trigger.monitoring_frequency}\n"
        f"Status Change: {old_status} → {new_status}\n\n"
        f"=== Trigger Description ===\n"
        f"{trigger.description}\n\n"
        f"=== Related Driver ===\n"
        f"{trigger.related_driver}\n\n"
        f"=== Condition Details ===\n"
        f"{condition_details}\n\n"
        f"=== Evaluation Results ===\n"
        f"Condition Met: {'YES' if evaluation.get('condition_met') else 'NO'}\n"
        f"Current Value: {evaluation.get('current_value', 'N/A')}\n"
        f"Threshold: {evaluation.get('threshold', 'N/A')}\n"
        f"Details: {evaluation.get('details', 'N/A')}\n"
        f"Evaluated At: {evaluation.get('evaluated_at', 'N/A')}\n\n"
        f"=== Source Information ===\n"
        f"Related Companies: {trigger.related_companies}\n"
        f"Industry: {trigger.related_industry}\n\n"
        f"Decision support only — verify primary sources before acting."
    )
    
    return _send(subject, body)


