"""Email notifications for material trigger state changes."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Dict, List

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
    # print("email_is_configured:")
    # print(bool(c["recipient"] and c["host"] and c["sender"]))
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
    # print(body)
    report_sent = _send(subject, body)

    return report_sent


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
        body = (
            f"Investment intelligence alert\n\n"
            f"Company: {company}\n"
            f"Trigger: {trigger.trigger_id}\n"
            f"Category: {trigger.category}\n"
            f"Status change: {old_status} → {trigger.status}\n"
            f"Trigger: {trigger.description}\n"
            f"Related driver: {trigger.related_driver}\n"
            f"Analyst assessment: {assessment.get('outcome', 'N/A')} ({assessment.get('impact', 'Unclear')})\n"
            f"Confidence: {assessment.get('confidence', 'N/A')}/100\n\n"
            f"Event / evidence:\n{event}\n\n"
            f"Recommendation: {assessment.get('recommendation', 'Review the evidence.')}\n\n"
            f"Decision support only — verify primary sources before acting."
        )
        delivery = _send(subject, body)
        record_alert(fingerprint, company, trigger.trigger_id, trigger.status, delivery, subject)
        set_trigger_status(company, trigger.trigger_id, trigger.status)
        outcomes.append(f"{trigger.trigger_id}: {delivery}")
    return outcomes


