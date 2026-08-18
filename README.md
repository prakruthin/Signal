# Signal — AI Investment Intelligence MVP

A Gradio application that turns a public company into a living, auditable investment thesis. It includes company research, bull/base/bear cases, success and failure drivers, automatically generated triggers, event evaluation, persisted thesis versions, and a live multi-agent research monitor.

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
│  • refresh_live_agents() - Runs live multi-agent scan                                │
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
│ • Investment    │          │                 │          │                 │
│   Analyst Agent │          │                 │          │                 │
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
         │    └────────┬─────────┘           └──────┬───────┘    │
         │             │                            │             │
         └─────────────┼────────────────────────────┼─────────────┘
                       │                            │
                       ▼                            ▼
              ┌─────────────────┐          ┌─────────────────┐
              │  NOTIFICATIONS  │          │  MONITOR CLI    │
              │  (notifications│          │  (monitor.py)   │
              │   .py)          │          │                 │
              │                 │          │ • Headless scan │
              │ • SMTP email    │          │ • Scheduler     │
              │ • Trigger alerts│          │ • Continuous    │
              │ • Research rpt  │          │   monitoring    │
              │ • Deduplication │          │                 │
              └─────────────────┘          └─────────────────┘
```

---

## File-by-File Breakdown

### Core Application Files

| File | Purpose | Key Functions/Classes |
|------|---------|----------------------|
| **app/main.py** | **Entry point & Gradio UI orchestrator** | `research()`, `assess_event()`, `refresh_live_agents()` - coordinates all modules, manages UI state, launches Gradio app |
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
| `generate_triggers()` | Creates monitoring triggers from thesis drivers. LLM-generated if configured, otherwise 1:1 from drivers. |
| `evaluate_event()` | Scores new event against thesis & triggers. Returns outcome, impact, confidence, recommendation. |
| `summarize_thesis()` | Formats thesis as Markdown for UI/email |
| `drivers_rows()`, `trigger_rows()` | Formats for Gradio Dataframe components |

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
| `generate_triggers_with_llm()` | Creates actionable monitoring triggers from drivers |
| `evaluate_with_llm()` | Evaluates new event against thesis & triggers |
| `assess_findings_with_llm()` | Synthesizes live agent findings for monitor |
| `discover_competitors()` | LLM-based competitor identification with threat levels |

**Prompt engineering**: Comprehensive 800+ line system prompt enforcing evidence-based reasoning, confidence scoring framework (0-100 based on evidence quality, not direction), mandatory financial statement incorporation, fact/interpretation/conclusion separation.

### Data Models (`app/models.py`)

**Purpose**: Dataclasses for type-safe data flow.

| Class | Fields |
|-------|--------|
| `Driver` | name, description, importance (1-10), direction (Pos/Neg/Neutral), monitoring_required, source_type |
| `Trigger` | trigger_id, category, description, confidence, importance, related_driver, related_companies, related_industry, monitoring_frequency, status |
| `Thesis` | company, industry, bull_case[], bear_case[], base_case, confidence, assumptions[], challenge, drivers[], competitors[] |

### Persistence Layer (`app/store.py`)

**Purpose**: SQLAlchemy ORM with SQLite (default) or PostgreSQL support.

| Table | Purpose |
|-------|---------|
| `thesis_versions` | Versioned thesis snapshots with change reason |
| `event_log` | All evaluated events with full evaluation JSON |
| `alert_deliveries` | Email delivery fingerprints (prevents duplicate alerts) |
| `trigger_states` | Persistent trigger status across monitor runs |

**Key functions**: `save_thesis()`, `thesis_history()`, `log_event()`, `alert_was_sent()`, `record_alert()`, `trigger_status()`, `set_trigger_status()`

### Notifications (`app/notifications.py`)

**Purpose**: SMTP email alerts with deduplication.

| Function | Description |
|----------|-------------|
| `email_is_configured()` | Validates SMTP config from `.env` |
| `send_research_report()` | Sends full thesis + profile + triggers on research completion |
| `notify_trigger_changes()` | Sends one email per trigger status change (Monitoring → Activated/Strengthened). Uses fingerprint (company|trigger|old|new|event) to prevent duplicates. |

### Headless Monitor (`app/monitor.py`)

**Purpose**: Run continuous monitoring without browser.

```bash
# One-time scan
python -m app.monitor --once

# Continuous (set MONITOR_INTERVAL_SECONDS in .env, default 300s)
python -m app.monitor
```

**Flow**: `scan()` → collects research if first run → builds thesis/triggers → runs live agents → sends alerts → logs → sleeps → repeats.

---

## Program Descriptions

### 1. **Gradio Web Application** (`python -m app.main`)
Interactive dashboard with 6 tabs:
- **Research Company** - Enter name/ticker → runs full pipeline → saves thesis v1
- **Investment Thesis** - Bull/base/bear cases, confidence, assumptions, challenge
- **Financial Analysis** - TTM + 4Y tables: performance, health, cash flow
- **Drivers & Triggers** - Thesis drivers (importance, direction, source) + auto-generated monitoring triggers
- **Evaluate Event** - Paste headline/filing → scores against thesis → updates trigger statuses → emails
- **Live Agent Monitor** - Runs 5 agents + LLM analyst → shows findings, assessment, updated triggers
- **Thesis History** - Versioned thesis snapshots

### 2. **Headless Monitor Service** (`python -m app.monitor`)
Production-grade background service:
- Runs on schedule (default 5 min interval)
- Persists thesis & triggers between runs
- Sends email alerts only on trigger state transitions
- Logs all scans to database
- Designed for systemd, Docker, or cron deployment

### 3. **Research Pipeline** (triggered by UI or monitor)
```
Company + Ticker
      │
      ▼
CompanyResearchAgent ──► Profile, market, history, headlines, competitors
      │
      ├─► MarketDataAgent ──► Live quote
      ├─► FinancialAgent ──► TTM + 4Y financials (income, balance, cash flow)
      ├─► NewsAgent ──► Company headlines
      ├─► CompetitorAgent ──► Competitor headlines
      └─► RegulatoryAgent ──► Policy headlines
      │
      ▼
All Findings ──► InvestmentAnalystAgent (LLM or keyword)
      │
      ▼
Thesis Built (LLM or deterministic) ──► Triggers Generated ──► Saved to DB ──► Email Report
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
| `MONITOR_INTERVAL_SECONDS` | No | Monitor interval (default 300) |

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

# 4. Or run headless monitor
python -m app.monitor --once        # Single scan
python -m app.monitor               # Continuous
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
| Scheduling | Built-in (monitor.py) or external (systemd/cron) |