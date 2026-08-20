"""Run the investment monitor without the Gradio interface.

Use this in a process manager or server so monitoring and email alerts continue
when nobody has the dashboard open.
"""

import argparse
import os
import time

from .agents import collect_full_research, run_live_agents
from .analyst import build_thesis, generate_triggers
from .notifications import notify_trigger_changes


def scan(company: str, ticker: str, triggers=None, thesis=None):
    resolved_ticker = ticker
    if thesis is None or triggers is None:
        bundle = collect_full_research(company, ticker)
        resolved_ticker = bundle["research"].get("ticker") or ticker
        thesis = build_thesis(company, ticker, bundle["research"], bundle["findings"])
        triggers = generate_triggers(thesis, bundle["findings"])
    before = {trigger.trigger_id: trigger.status for trigger in triggers}
    result = run_live_agents(thesis, resolved_ticker, triggers)
    assessment = result["assessment"]
    evidence = "\n".join(item["finding"] for item in result["findings"] if item["impact"] in ("Positive", "Negative"))
    deliveries = notify_trigger_changes(thesis.company, before, triggers, evidence or "Live multi-agent scan", assessment)
    print(f"{result['checked_at']} | {assessment['stance']} | alerts: {', '.join(deliveries) or 'none'}")
    return thesis, triggers


def main():
    parser = argparse.ArgumentParser(description="Signal Watch live monitoring and email alert service")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    args = parser.parse_args()
    company = os.getenv("MONITOR_COMPANY", "Vodafone Idea")
    ticker = os.getenv("MONITOR_TICKER", "IDEA.NS")
    interval = max(60, int(os.getenv("MONITOR_INTERVAL_SECONDS", "300")))
    thesis = None
    triggers = None
    while True:
        try:
            thesis, triggers = scan(company, ticker, triggers, thesis)
        except Exception as exc:
            print(f"Monitor scan failed: {type(exc).__name__}: {exc}")
        if args.once:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
