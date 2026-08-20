"""Automated trigger monitoring service with per-trigger scheduling."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .models import Trigger
from .store import (
    _session,
    _normalize_company,
    TriggerState,
    save_trigger_condition,
    get_trigger_condition,
    get_all_trigger_conditions,
    log_trigger_evaluation,
    set_trigger_status,
)
from .trigger_evaluator import TriggerEvaluator
from .notifications import notify_trigger_changes, email_is_configured


class TriggerMonitor:
    """Automated trigger monitoring with per-trigger scheduling."""
    
    def __init__(self, company: str, ticker: str, competitors: List[str], industry: str):
        self.company = company
        self.ticker = ticker
        self.competitors = competitors
        self.industry = industry
        self.evaluator = TriggerEvaluator()
        self.scheduler = BackgroundScheduler()
        self.running = False
        self._triggers_cache: Dict[str, Trigger] = {}
        self._conditions_cache: Dict[str, Dict] = {}
    
    def load_triggers(self) -> List[Trigger]:
        """Load triggers from database and memory cache."""
        session = _session()
        try:
            company = _normalize_company(self.company)
            trigger_states = session.query(TriggerState).filter_by(company=company).all()
            triggers = []
            for ts in trigger_states:
                trigger_id = ts.trigger_id
                condition = get_trigger_condition(trigger_id)
                # Include main company in related_companies for tracking
                related_companies = ", ".join([self.company] + self.competitors)
                trigger = Trigger(
                    trigger_id=trigger_id,
                    category="",
                    description=condition.get("description", "") if isinstance(condition, dict) else "",
                    confidence=0,
                    importance="Medium",
                    related_driver="",
                    related_companies=related_companies,
                    related_industry=self.industry,
                    monitoring_frequency="Daily",
                    status=ts.status,
                    condition=condition if condition else None,
                )
                triggers.append(trigger)
                self._triggers_cache[trigger_id] = trigger
                if condition:
                    self._conditions_cache[trigger_id] = condition
            return triggers
        finally:
            session.close()
    
    def schedule_trigger(self, trigger: Trigger) -> None:
        """Schedule a trigger for periodic evaluation."""
        if trigger.trigger_id in self._triggers_cache:
            existing_job = self.scheduler.get_job(trigger.trigger_id)
            if existing_job:
                existing_job.remove()
        
        freq = trigger.monitoring_frequency.lower()
        condition = trigger.condition or self._conditions_cache.get(trigger.trigger_id, {})
        
        if freq == "hours":
            trigger_args = {"hours": 1}
            trigger_type = IntervalTrigger
        elif freq == "daily":
            trigger_args = {"hour": 6, "minute": 0}
            trigger_type = CronTrigger
        elif freq == "weekly":
            trigger_args = {"day_of_week": "mon", "hour": 6, "minute": 0}
            trigger_type = CronTrigger
        elif freq == "monthly":
            trigger_args = {"day": 1, "hour": 6, "minute": 0}
            trigger_type = CronTrigger
        else:
            trigger_args = {"hours": 1}
            trigger_type = IntervalTrigger
        
        job = self.scheduler.add_job(
            self._evaluate_single_trigger,
            trigger_type(**trigger_args),
            args=[trigger.trigger_id],
            id=trigger.trigger_id,
            name=f"Trigger {trigger.trigger_id}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        print(f"Scheduled trigger {trigger.trigger_id} ({trigger.monitoring_frequency}): {job.next_run_time}")
    
    def _evaluate_single_trigger(self, trigger_id: str) -> None:
        """Evaluate a single trigger by ID."""
        trigger = self._triggers_cache.get(trigger_id)
        if not trigger:
            print(f"Trigger {trigger_id} not found in cache, reloading...")
            self.load_triggers()
            trigger = self._triggers_cache.get(trigger_id)
            if not trigger:
                print(f"Trigger {trigger_id} still not found, skipping")
                return
        
        print(f"[{datetime.now(timezone.utc).isoformat()}] Evaluating trigger {trigger_id}...")
        
        try:
            evaluation = self.evaluator.evaluate_trigger(
                trigger, self.company, self.ticker, self.competitors, self.industry
            )
            
            evaluation.trigger_id = trigger_id
            log_trigger_evaluation(evaluation.to_dict() if hasattr(evaluation, 'to_dict') else {
                "trigger_id": evaluation.trigger_id,
                "evaluated_at": evaluation.evaluated_at,
                "condition_met": evaluation.condition_met,
                "current_value": evaluation.current_value,
                "threshold": evaluation.threshold,
                "details": evaluation.details,
                "alert_sent": evaluation.alert_sent,
                "previous_status": evaluation.previous_status,
                "new_status": evaluation.new_status,
            })
            
            if evaluation.new_status != evaluation.previous_status:
                print(f"  Status change: {evaluation.previous_status} -> {evaluation.new_status}")
                set_trigger_status(self.company, trigger_id, evaluation.new_status)
                trigger.status = evaluation.new_status
                
                if email_is_configured():
                    self._send_alert(trigger, evaluation)
            else:
                print(f"  No status change (still {evaluation.new_status})")
                
        except Exception as e:
            print(f"  Error evaluating trigger {trigger_id}: {type(e).__name__}: {e}")
    
    def _send_alert(self, trigger: Trigger, evaluation) -> None:
        """Send email alert for trigger status change."""
        try:
            from .notifications import _send
            subject = f"{evaluation.new_status} — {self.company} — {trigger.trigger_id}"
            body = (
                f"Trigger Alert\n\n"
                f"Company: {self.company}\n"
                f"Trigger: {trigger.trigger_id}\n"
                f"Category: {trigger.category}\n"
                f"Status change: {evaluation.previous_status} → {evaluation.new_status}\n"
                f"Description: {trigger.description}\n"
                f"Related driver: {trigger.related_driver}\n"
                f"Condition: {evaluation.details}\n"
                f"Current value: {evaluation.current_value}\n"
                f"Threshold: {evaluation.threshold}\n"
                f"Evaluated: {evaluation.evaluated_at}\n\n"
                f"Decision support only — verify primary sources before acting."
            )
            result = _send(subject, body)
            print(f"  Alert sent: {result}")
        except Exception as e:
            print(f"  Failed to send alert: {type(e).__name__}: {e}")
    
    def run_all_now(self) -> None:
        """Run all triggers immediately (for testing or manual run)."""
        triggers = self.load_triggers()
        for trigger in triggers:
            self._evaluate_single_trigger(trigger.trigger_id)
    
    def start(self) -> None:
        """Start the scheduler."""
        if self.running:
            return
        
        triggers = self.load_triggers()
        for trigger in triggers:
            self.schedule_trigger(trigger)
        
        self.scheduler.start()
        self.running = True
        print(f"Trigger monitor started for {self.company} with {len(triggers)} triggers")
    
    def stop(self) -> None:
        """Stop the scheduler."""
        if not self.running:
            return
        self.scheduler.shutdown(wait=True)
        self.running = False
        print("Trigger monitor stopped")
    
    def status(self) -> Dict[str, Any]:
        """Get monitor status."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return {
            "company": self.company,
            "running": self.running,
            "triggers_loaded": len(self._triggers_cache),
            "jobs": jobs,
        }


def run_monitor(
    company: str = "Vodafone Idea",
    ticker: str = "IDEA.NS",
    competitors: Optional[List[str]] = None,
    industry: str = "Telecommunications",
    once: bool = False,
) -> None:
    """Run the trigger monitor."""
    if competitors is None:
        competitors = ["Bharti Airtel", "Reliance Jio", "BSNL"]
    
    monitor = TriggerMonitor(company, ticker, competitors, industry)
    
    def signal_handler(signum, frame):
        print("\nShutdown signal received...")
        monitor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if once:
        print(f"Running one-time evaluation for {company}...")
        monitor.load_triggers()
        monitor.run_all_now()
    else:
        print(f"Starting continuous monitor for {company}...")
        monitor.start()
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            monitor.stop()


def main():
    parser = argparse.ArgumentParser(description="Signal Watch Trigger Monitor - Automated per-trigger monitoring")
    parser.add_argument("--once", action="store_true", help="Run all triggers once and exit")
    parser.add_argument("--company", default=os.getenv("MONITOR_COMPANY", "Vodafone Idea"))
    parser.add_argument("--ticker", default=os.getenv("MONITOR_TICKER", "IDEA.NS"))
    parser.add_argument("--industry", default=os.getenv("MONITOR_INDUSTRY", "Telecommunications"))
    parser.add_argument("--competitors", default=os.getenv("MONITOR_COMPETITORS", ""))
    
    args = parser.parse_args()
    
    competitors = [c.strip() for c in args.competitors.split(",") if c.strip()] if args.competitors else None
    
    run_monitor(
        company=args.company,
        ticker=args.ticker,
        competitors=competitors,
        industry=args.industry,
        once=args.once,
    )


if __name__ == "__main__":
    main()