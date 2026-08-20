# Signal Watch — AI Investment Intelligence MVP

A Gradio application that turns a public company into a living, auditable investment thesis. It includes company research, bull/base/bear cases, success and failure drivers, automatically generated triggers with structured conditions, event evaluation, persisted thesis versions, and a **per-trigger automated monitoring service** with email alerts.

---

## System Architecture Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE (Gradio)                                    │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │  Research   │ │  Investment  │ │  Financial      │ │  Drivers &  │ │  Evaluate │ │
│  │  Company    │ │  Thesis      │ │  Analysis       │ │  Triggers   │ │  Event    │ │
│  └──────┬──────┘ └──────┬───────┘ └────────┬────────┘ └──────┬──────┘ └─────┬─────┘ │
└─────────┼───────────────┼──────────────────┼────────────────┼──────────────┼───────┘
          │               │                  │                │              │
          ▼               ▼                  ▼                ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         CORE ORCHESTRATION (main.py)                                 │
│  • research() - Runs full pipeline: collect → thesis → triggers → save → email     │
│  • assess_event() - Evaluates new events against thesis & triggers                  │
│  • refresh_trigger_monitor() - Evaluates tracked triggers against live data        │
└──────────────────────────────────────┬──────────────────────────────────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          ▼                            ▼                            ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  AGENTS MODULE  │          │  ANALYST MODULE │          │ FINANCIAL AGENT │
│  (agents.py)    │          │  (analyst.py)   │          │ (financial_     │
│                 │          │                 │          │  agent.py)      │
│ • CompanyResearch│         │ • build_thesis()│          │ • FinancialAgent│
│   Agent         │          │ • generate_     │          │   collects TTM  │
│ • MarketData    │          │   triggers()    │          │   & 4Y financials│
│   Agent         │          │ • evaluate_     │          │ • Income stmt,  │
│ • NewsAgent     │          │   event()       │          │   balance sheet,│
│ • Competitor    │          │ • summarize_    │          │   cash flow     │
│   Agent         │          │   thesis()      │          │ • Computes ratios│
│ • Regulatory    │          │ • drivers_rows()│          │   & growth      │
│   Agent         │          │ • trigger_rows()│          │                 │
│ • Investment    │          │ • _build_driver_│          │                 │
│   Analyst Agent │          │   condition()   │          │                 │
└────────┬────────┘          └────────┬────────┘          └────────┬────────┘
         │                            │                            │
         │              ┌─────────────┴─────────────┐             │
         │              ▼                           ▼             │
         │    ┌──────────────────┐           ┌──────────────┐    │
         │    │   LLM MODULE     │           │  STORE MODULE│    │
         │    │   (llm.py)       │           │  (store.py)  │    │
         │    │                  │           │              │    │
         │    │ • Thesis gen     │           │ • SQLite/    │    │
         │    │ • Trigger gen    │           │   PostgreSQL │    │
         │    │ • Event eval     │           │ • Thesis     │    │
         │    │ • Findings synth │           │   versions   │    │
         │    │ • Competitor disc│           │ • Event log  │    │
         │    │                  │           │ • Alert      │    │
         │    │                  │           │   delivery   │    │
         │    │                  │           │ • Trigger    │    │
         │    │                  │           │   state      │    │
         │    │                  │           │ • Trigger    │    │
         │    │                  │           │   conditions │    │
         │    │                  │           │ • Metric     │    │
         │    │                  │           │   history    │    │
         │    │                  │           │ • Trigger    │    │
         │    │                  │           │   evaluations│    │
         │    └────────┬─────────┘           └──────┬───────┘    │
         │             │                            │             │
         └─────────────┼────────────────────────────┼─────────────┘
                       │                            │
                       ▼                            ▼
              ┌─────────────────┐          ┌─────────────────┐
              │  NOTIFICATIONS  │          │  TRIGGER MONITOR│
              │  (notifications│          │  (trigger_mon-  │
              │   .py)          │          │   itor.py)      │
              │                 │          │                 │
              │ • SMTP email    │          │ • APScheduler   │
              │ • Trigger alerts│          │ • Per-trigger   │
              │ • Research rpt  │          │   frequency     │
              │ • Deduplication │          │ • Auto-eval     │
              └─────────────────┘          └─────────────────┘
```

---

## New: Automated Trigger Monitoring System

### Key Features

| Feature | Description |
|---------|-------------|
| **Per-trigger scheduling** | Each trigger runs on its own frequency (Hours/Daily/Weekly/Monthly) via APScheduler |
| **Structured conditions** | Triggers have machine-evaluable conditions (not free-text) |
| **5 condition types** | `financial_metric`, `news_keyword`, `news_sentiment`, `news_volume`, `price_change` |
| **Historical tracking** | `metric_history` table stores time-series for consecutive-period conditions |
| **Evaluation audit trail** | `trigger_evaluations` table logs every check with values, met/not-met, status changes |
| **Email alerts** | Detailed emails on status changes (Monitoring → Activated/Strengthened) with condition explanation |
| **Opt-in tracking** | User chooses which triggers to monitor via "Start Tracking" button |
| **Company normalization** | Consistent company name handling across all database operations |

### Condition Types

| Type | Data Source | Example |
|------|-------------|---------|
| `financial_metric` | Yahoo Finance financials | `revenue_growth_ttm < 5%` for 2 consecutive quarters |
| `news_keyword` | Google/Yahoo RSS | Headlines containing "bankruptcy", "FDA approval" in last 7 days |
| `news_sentiment` | Google/Yahoo RSS | ≥3 negative headlines (sentiment < -0.3) in 7 days |
| `news_volume` | Google/Yahoo RSS | Headline count > 2x 30-day average (min 5) |
| `price_change` | Yahoo Finance price | Price change > 10% in single day |

---

## File-by-File Breakdown

### Core Application Files

| File | Purpose | Key Functions/Classes |
|------|---------|----------------------|
| **app/main.py** | **Entry point & Gradio UI orchestrator** | `research()`, `assess_event()`, `refresh_trigger_monitor()`, `start_tracking_trigger()` - coordinates all modules, manages UI state, launches Gradio app |
| **app/__init__.py** | Package marker | Empty - makes `app` a Python package |

### Data Collection Agents (`app/agents.py`)

**Purpose**: Five transparent, source-attributed research agents with safe offline fallbacks.

| Agent | Source | What It Collects |
|-------|--------|------------------|
| `CompanyResearchAgent` | Yahoo Finance search, Wikipedia, Google News RSS | Company profile, ticker, exchange, industry, market snapshot, 1-year price history, headlines |
| `MarketDataAgent` | Yahoo Finance chart API | Live quote, price change vs prior close, impact classification |
| `NewsAgent` | Google News RSS | Recent company headlines (10 items) with impact scoring |
| `CompetitorAgent` | Google News RSS | Competitor-specific headlines using dynamic competitor list |
| `RegulatoryAgent` | Google News RSS | Policy/regulation headlines for company + industry |
| `InvestmentAnalystAgent` | LLM (OpenAI) or keyword fallback | Synthesizes all findings against thesis & triggers |

**Helper functions**:
- `collect_full_research()` - Runs all collectors for initial thesis building
- `run_live_agents()` - Runs live scan for monitoring
- `findings_rows()`, `assessment_markdown()` - UI formatting

### Thesis Construction & Analysis (`app/analyst.py`)

**Purpose**: Builds evidence-based investment thesis from live research data.

| Function | Description |
|----------|-------------|
| `build_thesis()` | Creates Thesis object: bull/bear/base cases, confidence (15-90), assumptions, challenge, drivers. Uses LLM if configured, otherwise deterministic logic from financial signals + headlines. |
| `company_snapshot()` | Formats company profile for UI/email (price, 52w range, YTD, sources) |
| `generate_triggers()` | Creates monitoring triggers from thesis drivers. LLM-generated if configured, otherwise 1:1 from drivers with structured conditions via `_build_driver_condition()`. |
| `evaluate_event()` | Scores new event against thesis & triggers. Returns outcome, impact, confidence, recommendation. |
| `summarize_thesis()` | Formats thesis as Markdown for UI/email |
| `drivers_rows()`, `trigger_rows()` | Formats for Gradio Dataframe components |
| `_build_driver_condition()` | **NEW**: Maps driver names to financial metrics with appropriate thresholds for fallback triggers |

### Financial Analysis (`app/financial_agent.py`)

**Purpose**: Deep financial statement analysis using yfinance (Yahoo Finance).

| Component | Description |
|-----------|-------------|
| `FinancialAgent.collect()` | Fetches TTM + 4 fiscal years: income statement, balance sheet, cash flow. Computes margins, growth, leverage, FCF metrics. Returns `FinancialSnapshot` + agent findings. |
| `FinancialSnapshot` | Dataclass holding all financial data by period (TTM, FY-1..FY-4) |
| `financial_thesis_signals()` | Derives bull/bear points & drivers from financials for non-LLM thesis fallback |
| `financial_markdown()` | Renders financial tables for Gradio UI |
| `financial_thesis_context()` | Structured text for LLM thesis generation |

**Metrics computed**: Revenue, growth, gross/operating/EBITDA margins, net income, EPS, cash, debt, net debt, working capital, debt/equity, debt/assets, operating cash flow, CapEx, FCF, FCF margin, FCF growth, FCF conversion.

### LLM Integration (`app/llm.py`)

**Purpose**: All AI-powered analysis using OpenAI-compatible API.

| Function | Purpose |
|----------|---------|
| `llm_is_configured()` | Checks for `OPENAI_API_KEY` |
| `build_thesis_with_llm()` | Senior analyst prompt → full thesis JSON |
| `generate_triggers_with_llm()` | **UPDATED**: Creates actionable monitoring triggers with structured `condition` objects (5 condition types) |
| `evaluate_with_llm()` | Evaluates new event against thesis & triggers |
| `assess_findings_with_llm()` | Synthesizes live agent findings for monitor |
| `discover_competitors()` | LLM-based competitor identification with threat levels |

**Prompt engineering**: Comprehensive system prompt enforcing evidence-based reasoning, confidence scoring framework (0-100 based on evidence quality, not direction), mandatory financial statement incorporation, fact/interpretation/conclusion separation. **Trigger generation now requires structured `condition` object** matching one of 5 condition types.

### New Modules

| File | Purpose |
|------|---------|
| **app/trigger_conditions.py** | Condition parsing, validation, evaluation logic for 5 condition types. Includes `parse_condition()`, `validate_condition()`, `evaluate_financial_condition()`, `evaluate_news_keyword_condition()`, `evaluate_news_sentiment_condition()`, `evaluate_news_volume_condition()`, `evaluate_price_condition()` |
| **app/data_fetchers.py** | `YahooFinanceFetcher` (financials, price, historical metrics) + `RSSFetcher` (Google News, Yahoo Finance RSS). Handles caching, error handling, impact classification. |
| **app/trigger_evaluator.py** | `TriggerEvaluator` class - evaluates triggers against live data sources. `evaluate_trigger()` routes to appropriate evaluator based on condition type. `evaluate_all_triggers()` runs batch evaluation. Persists results to `trigger_evaluations` and `metric_history` tables. |
| **app/trigger_monitor.py** | Background service with APScheduler for per-trigger scheduling. Loads triggers from DB, schedules each per its frequency, runs evaluations, sends alerts, updates status. Run with `python -m app.trigger_monitor --once` or continuous. |

### Thesis Construction & Analysis (`app/analyst.py`)

**Purpose**: Builds evidence-based investment thesis from live research data.

| Function | Description |
|----------|-------------|
| `build_thesis()` | Creates Thesis object: bull/bear/base cases, confidence (15-90), assumptions, challenge, drivers. Uses LLM if configured, otherwise deterministic logic from financial signals + headlines. |
| `company_snapshot()` | Formats company profile for UI/email (price, 52w range, YTD, sources) |
| `generate_triggers()` | Creates monitoring triggers from thesis drivers. LLM-generated if configured, otherwise 1:1 from drivers with structured conditions via `_build_driver_condition()`. |
| `evaluate_event()` | Scores new event against thesis & triggers. Returns outcome, impact, confidence, recommendation. |
| `summarize_thesis()` | Formats thesis as Markdown for UI/email |
| `drivers_rows()`, `trigger_rows()` | Formats for Gradio Dataframe components |
| `_build_driver_condition()` | **NEW**: Maps driver names to financial metrics with appropriate thresholds for fallback triggers (e.g., "Revenue growth" → `revenue_growth_ttm < 5%` for 2 quarters) |

### Financial Analysis (`app/financial_agent.py`)

**Purpose**: Deep financial statement analysis using yfinance (Yahoo Finance).

| Component | Description |
|-----------|-------------|
| `FinancialAgent.collect()` | Fetches TTM + 4 fiscal years: income statement, balance sheet, cash flow. Computes margins, growth, leverage, FCF metrics. Returns `FinancialSnapshot` + agent findings. |
| `FinancialSnapshot` | Dataclass holding all financial data by period (TTM, FY-1..FY-4) |
| `financial_thesis_signals()` | Derives bull/bear points & drivers from financials for non-LLM thesis fallback |
| `financial_markdown()` | Renders financial tables for Gradio UI |
| `financial_thesis_context()` | Structured text for LLM thesis generation |

**Metrics computed**: Revenue, growth, gross/operating/EBITDA margins, net income, EPS, cash, debt, net debt, working capital, debt/equity, debt/assets, operating cash flow, CapEx, FCF, FCF margin, FCF growth, FCF conversion.

### LLM Integration (`app/llm.py`)

**Purpose**: All AI-powered analysis using OpenAI-compatible API.

| Function | Purpose |
|----------|---------|
| `llm_is_configured()` | Checks for `OPENAI_API_KEY` |
| `build_thesis_with_llm()` | Senior analyst prompt → full thesis JSON |
| `generate_triggers_with_llm()` | **UPDATED**: Creates actionable monitoring triggers with structured `condition` objects (5 condition types: financial_metric, news_keyword, news_sentiment, news_volume, price_change) |
| `evaluate_with_llm()` | Evaluates new event against thesis & triggers |
| `assess_findings_with_llm()` | Synthesizes live agent findings for monitor |
| `discover_competitors()` | LLM-based competitor identification with threat levels |

**Prompt engineering**: Comprehensive system prompt enforcing evidence-based reasoning, confidence scoring framework (0-100 based on evidence quality, not direction), mandatory financial statement incorporation, fact/interpretation/conclusion separation. **Trigger generation now requires structured `condition` object** matching one of 5 condition types with detailed validation checklist and examples.

### Data Models (`app/models.py`)

**Purpose**: Dataclasses for type-safe data flow.

| Class | Fields |
|-------|--------|
| `Driver` | name, description, importance (1-10), direction (Pos/Neg/Neutral), monitoring_required, source_type |
| `Trigger` | trigger_id, category, description, confidence, importance, related_driver, related_companies, related_industry, monitoring_frequency, status, **condition** (dict), **cooldown_until** |
| `TriggerCondition` | **NEW**: trigger_id, condition_type, metric_name, operator, threshold, unit, lookback_periods, period_type, consecutive, allow_gaps, keywords[], sentiment_threshold, volume_multiplier, data_source, metadata fields |
| `MetricHistory` | **NEW**: company, metric_name, value, period_end, period_type, source |
| `TriggerEvaluation` | **NEW**: trigger_id, evaluated_at, condition_met, current_value, threshold, details, alert_sent, previous_status, new_status |
| `Thesis` | company, industry, bull_case[], bear_case[], base_case, confidence, assumptions[], challenge, drivers[], competitors[] |

### Persistence Layer (`app/store.py`)

**Purpose**: SQLAlchemy ORM with SQLite (default) or PostgreSQL support.

| Table | Purpose |
|-------|---------|
| `thesis_versions` | Versioned thesis snapshots with change reason |
| `event_log` | All evaluated events with full evaluation JSON |
| `alert_deliveries` | Email delivery fingerprints (prevents duplicate alerts) |
| `trigger_states` | Persistent trigger status across monitor runs |
| `trigger_conditions` | **NEW**: Structured trigger conditions + metadata (description, category, confidence, importance, related_driver, monitoring_frequency, status) |
| `metric_history` | **NEW**: Time-series of financial metrics for consecutive-period conditions |
| `trigger_evaluations` | **NEW**: Evaluation audit trail (condition_met, current_value, threshold, details, status transitions) |

**Key functions**: `save_thesis()`, `thesis_history()`, `log_event()`, `alert_was_sent()`, `record_alert()`, `trigger_status()`, `set_trigger_status()`, `save_trigger_condition()`, `get_trigger_condition()`, `get_all_trigger_conditions()`, `get_all_companies_with_triggers()`, `store_metric_history()`, `get_metric_history()`, `log_trigger_evaluation()`, `get_trigger_evaluations()`

**Company normalization**: All company-name operations use `_normalize_company()` for consistent storage/querying.

### Notifications (`app/notifications.py`)

**Purpose**: SMTP email alerts with deduplication.

| Function | Description |
|----------|-------------|
| `email_is_configured()` | Validates SMTP config from `.env` |
| `send_research_report()` | Sends full thesis + profile + triggers on research completion |
| `notify_trigger_changes()` | Sends one email per trigger status change (Monitoring → Activated/Strengthened). Uses fingerprint (company|trigger|old|new|event) to prevent duplicates. |
| `_format_trigger_condition()` | **NEW**: Formats structured condition details for email (type, metric, threshold, lookback, etc.) |
| `send_trigger_evaluation_alert()` | **NEW**: Detailed alert for automated trigger evaluation with condition explanation |

### Trigger Monitor Service (`app/trigger_monitor.py`)

**Purpose**: Automated per-trigger monitoring with APScheduler.

```bash
# One-time evaluation
python -m app.trigger_monitor --once --company "Vodafone Idea" --ticker "IDEA.NS"

# Continuous (per-trigger frequencies: Hours/Daily/Weekly/Monthly)
python -m app.trigger_monitor --company "Vodafone Idea" --ticker "IDEA.NS"
```

**Features**:
- Loads triggers from `trigger_states` + `trigger_conditions` tables
- Schedules each trigger per its `monitoring_frequency` (Hours→interval 1h, Daily→cron 6AM, Weekly→cron Mon 6AM, Monthly→cron 1st 6AM)
- Runs `TriggerEvaluator.evaluate_trigger()` on schedule
- On status change: updates `trigger_states`, logs to `trigger_evaluations`, sends detailed email
- 24-hour cooldown prevents alert flapping
- Designed for systemd, Docker, or cron deployment

### Headless Monitor (`app/monitor.py`)

**Purpose**: Legacy continuous monitoring (single interval for all triggers).

```bash
# One-time scan
python -m app.monitor --once

# Continuous (set MONITOR_INTERVAL_SECONDS in .env, default 300s)
python -m app.monitor
```

**Note**: This uses the old LLM-based qualitative assessment. The new `trigger_monitor.py` is recommended for production.

---

## Gradio UI Tabs (6 total)

| Tab | Description |
|-----|-------------|
| **Research Company** | Enter name/ticker → runs full pipeline → saves thesis v1 |
| **Investment Thesis** | Bull/base/bear cases (structured), confidence, assumptions, challenge |
| **Financial Analysis** | TTM + 4Y tables: performance, health, cash flow |
| **Drivers & Triggers** | Thesis drivers + auto-generated triggers. **Dropdown + "Start Tracking" button** to opt-in triggers for monitoring |
| **Evaluate Event** | Paste headline/filing → scores against thesis → updates trigger statuses → emails |
| **Trigger Monitor** | **NEW**: Company dropdown (from DB), "Refresh trigger status" button, table with ID, Category, Description, Importance, Frequency, Status, Condition, Last Evaluation, Next Check |

**Removed**: Live Agent Monitor tab, Thesis History tab

---

## User Workflow

```
1. Research Company
       │
       ▼
2. Review Thesis + Triggers (Drivers & Triggers tab)
       │
       ▼
3. Click "Start Tracking" on desired triggers
       │
       ▼
4. Trigger Monitor tab → Select company → "Refresh trigger status"
       │
       ▼
5. Background monitor (trigger_monitor.py) evaluates on schedule
       │
       ▼
6. Email alerts on status changes with detailed condition explanation
```

---

## Configuration (`.env`)

Copy `.env.example` to `.env` and configure:

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | No | SQLite (default) or PostgreSQL |
| `OPENAI_API_KEY` | For LLM | Enables AI thesis, triggers, event eval, competitor discovery |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |
| `OPENAI_BASE_URL` | No | Azure/OpenAI-compatible endpoint |
| `ALERT_RECIPIENT` | For email | Email address for alerts |
| `ALERT_FROM` | For email | Sender address |
| `SMTP_HOST` | For email | e.g., `smtp.office365.com` |
| `SMTP_PORT` | For email | Default 587 |
| `SMTP_USERNAME` | For email | SMTP login |
| `SMTP_PASSWORD` | For email | App password |
| `MONITOR_COMPANY` | For monitor | Default company to watch |
| `MONITOR_TICKER` | For monitor | Default ticker |
| `MONITOR_INDUSTRY` | For monitor | Default industry |
| `MONITOR_COMPETITORS` | For monitor | Comma-separated competitors |
| `MONITOR_INTERVAL_SECONDS` | No | Legacy monitor interval (default 300) |

---

## Quick Start

```bash
# 1. Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure (optional - works with demo data without API keys)
cp .env.example .env
# Edit .env for LLM + email

# 3. Run web UI
GRADIO_SERVER_PORT=8010 python -m app.main

# 4. Or run automated trigger monitor
python -m app.trigger_monitor --once --company "Tesla, Inc." --ticker "TSLA"
python -m app.trigger_monitor --company "Tesla, Inc." --ticker "TSLA"  # Continuous
```

Open browser to `http://localhost:8010` (or configured port). Try "Vodafone Idea" to load the demo profile.

---

## MVP Boundaries

- **Decision support only** — not financial advice
- **Deterministic fallback** — works without API keys using keyword-based analysis
- **Source transparency** — every finding shows agent, status (Live/Unavailable/Skipped), source, timestamp
- **No stale data** — unavailable sources reported explicitly
- **Extensible** — LLM prompts, agents, and storage ready for production connectors

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Web UI | Gradio 5.x |
| Database | SQLAlchemy 2.x + SQLite / PostgreSQL |
| Financial Data | yfinance (Yahoo Finance) |
| Market Data | Yahoo Finance chart API + RSS |
| News | Google News RSS + Yahoo Finance RSS |
| Company Info | Wikipedia API |
| LLM | OpenAI API (configurable model/endpoint) |
| Email | SMTP (Office365, Gmail, etc.) |
| Scheduling | APScheduler (trigger_monitor.py) or external (systemd/cron) |
| Time-series | Custom `metric_history` table for consecutive-period conditions |