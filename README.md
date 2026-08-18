# Signal — AI Investment Intelligence MVP

A Gradio application that turns a public company into a living, auditable investment thesis. It includes company research, bull/base/bear cases, success and failure drivers, automatically generated triggers, event evaluation, persisted thesis versions, and a live multi-agent research monitor.

## Live agent monitor

The monitor runs five transparent roles on demand:

- **Market Data Agent** fetches the current quote from Yahoo Finance.
- **Company News Agent** collects recent company headlines from Google News RSS.
- **Competitor Intelligence Agent** scans competitor-related headlines.
- **Regulatory & Policy Agent** scans relevant policy and regulatory headlines.
- **Investment Analyst Agent** synthesizes the evidence and maps it to the current thesis and triggers.

Every finding displays its source, retrieval status, and UTC timestamp. If a provider is unavailable, the monitor reports that explicitly instead of presenting stale data as live. It is research support, not financial advice.

## Email alerts

Copy `.env.example` to `.env` and fill in `ALERT_RECIPIENT` and the SMTP fields. The monitor sends a separate email whenever a trigger transitions, such as `Monitoring → Activated` or `Monitoring → Strengthened`. Deliveries are fingerprinted in the database to prevent duplicate notifications for the same event and state change.

Run continuous monitoring without the browser open:

```bash
set -a; source .env; set +a
python -m app.monitor
```

For a single scheduled scan, use `python -m app.monitor --once`. Keep the monitor running under a process manager, container, or scheduled job for continuous alerts.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
GRADIO_SERVER_PORT=8010 python -m app.main
```

Open the local address shown in the terminal. Set `GRADIO_SERVER_PORT` to any available local port if `8010` is in use. Start with `Vodafone Idea` to load the included telecom-focused demonstration profile.

## Storage

By default, data is stored in a local SQLite database named `investment_intelligence.db`. For PostgreSQL, copy `.env.example` to `.env`, set `DATABASE_URL`, and load it in your shell before launching.

## MVP boundaries

The interface and persistence layer are ready for live source connectors, LLM research, scheduled monitoring, and email delivery. The present MVP intentionally uses deterministic analyst logic and explicit demo data so it is usable without API credentials. It is decision support, not investment advice.
