import os
import gradio as gr
from .agents import assessment_markdown, collect_full_research, findings_rows
from .analyst import build_thesis, company_snapshot, drivers_rows, evaluate_event, generate_triggers, summarize_thesis, trigger_rows
from .financial_agent import financial_markdown
from .llm import llm_is_configured
from .notifications import email_is_configured, notify_trigger_changes, send_research_report
from .store import save_thesis, set_trigger_status, save_trigger_condition, get_all_companies_with_triggers, get_trigger_condition, trigger_status
from .trigger_evaluator import TriggerEvaluator
from .trigger_conditions import frequency_to_scheduler_args


COMPANY_TICKERS = {"vodafone idea": "IDEA.NS"}


def trigger_rows_with_tracking(triggers, company="", ticker=""):
    """Generate trigger rows with a 'Track' button column."""
    rows = []
    for t in triggers:
        # Check if already tracked in DB
        tracked = False
        if company:
            tracked = trigger_status(company, t.trigger_id) is not None
        track_label = "✓ Tracked" if tracked else "Start Tracking"
        rows.append([
            t.trigger_id,
            company,
            ticker,
            t.category,
            t.description[:80] + "..." if len(t.description) > 80 else t.description,
            t.confidence,
            t.importance,
            t.related_driver,
            t.monitoring_frequency,
            t.status,
            track_label,
        ])
    return rows


def research(company, ticker):
    if not company or not company.strip():
        raise gr.Error("Enter a publicly traded company to begin research.")
    ticker = ticker.strip() or COMPANY_TICKERS.get(company.strip().lower(), "")
    bundle = collect_full_research(company, ticker)
    research_data = bundle["research"]
    findings = bundle["findings"]
    thesis = build_thesis(company, ticker, research_data, findings)
    # print(thesis)
    triggers = generate_triggers(thesis, findings)
    summary = summarize_thesis(thesis)
    version = save_thesis(thesis.company, summary)
    
    # Do NOT auto-persist triggers - user must choose which to track
    # Triggers are only in session state until user clicks "Start Tracking"
    
    profile = company_snapshot(thesis, research_data)
    email_result = send_research_report(
        company=company,
        summary=summary,
        profile=profile,
        triggers=triggers,
    )
    profile_md = "\n".join(f"**{key}:** {value}" for key, value in profile.items())
    live_count = sum(1 for f in findings if f.get("status") == "Live")
    llm_note = "LLM analysis enabled." if llm_is_configured() else "Set OPENAI_API_KEY in .env to enable LLM thesis generation."
    status = (
        f"Research complete • {live_count} live agent findings • thesis v{version} saved • "
        f"{len(triggers)} LLM-generated triggers available. {llm_note}"
        f"Research email: {email_result}. "
    )
    trigger_choices = [t.trigger_id for t in triggers]
    return (
        summary,
        profile_md,
        financial_markdown(research_data.get("financials") or {}),
        drivers_rows(thesis),
        trigger_rows_with_tracking(triggers, thesis.company, ticker),
        {"thesis": thesis, "triggers": triggers, "ticker": research_data.get("ticker") or ticker, "research": research_data, "findings": findings, "user_company": company.strip()},
        status,
        gr.update(choices=trigger_choices, value=trigger_choices[0] if trigger_choices else None),
    )


def assess_event(event, state):
    if not state or "thesis" not in state:
        raise gr.Error("Run company research first.")
    if not event or not event.strip():
        raise gr.Error("Paste an event, filing update, headline, or earnings note.")
    thesis, triggers = state["thesis"], state["triggers"]
    ticker = state.get("ticker", "")
    before = {trigger.trigger_id: trigger.status for trigger in triggers}
    result, activated = evaluate_event(event, thesis, triggers)
    for trigger in activated:
        trigger.status = "Activated" if result["impact"] == "Negative" else "Strengthened"
    deliveries = notify_trigger_changes(thesis.company, before, triggers, event, result)
    delivery_note = "No trigger status changed; no email required." if not deliveries else "Email delivery: " + "; ".join(deliveries)
    md = f"## {result['outcome']}\n\n**Impact:** {result['impact']}  \n**Confidence:** {result['confidence']}/100  \n**Evaluated:** {result['evaluated_at']}\n\n**Recommendation:** {result['recommendation']}\n\n**{delivery_note}**\n\n**Evidence note:** {result['evidence']}"
    return md, trigger_rows_with_tracking(triggers, thesis.company, ticker), state


def start_tracking_trigger(trigger_id, state):
    """Persist a trigger to database for tracking."""
    if not state or "thesis" not in state:
        return "Run company research first.", trigger_rows_with_tracking(state.get("triggers", []), "", ""), gr.update()
    
    triggers = state["triggers"]
    thesis = state["thesis"]
    # Use the original user-entered company name for DB storage
    company = state.get("user_company", thesis.company)
    ticker = state.get("ticker", "")
    
    # Find the trigger (trigger_id is now direct, no parsing needed)
    trigger = next((t for t in triggers if t.trigger_id == trigger_id), None)
    if not trigger:
        trigger_choices = [t.trigger_id for t in triggers]
        return f"Trigger {trigger_id} not found.", trigger_rows_with_tracking(triggers, company, ticker), gr.update(choices=trigger_choices, value=trigger_id)
    
    # Check if already tracked
    existing_status = trigger_status(company, trigger_id)
    if existing_status is not None:
        trigger_choices = [t.trigger_id for t in triggers]
        return f"Trigger {trigger_id} is already being tracked.", trigger_rows_with_tracking(triggers, company, ticker), gr.update(choices=trigger_choices, value=trigger_id)
    
    # Persist to database
    set_trigger_status(company, trigger_id, trigger.status)
    
    # Merge trigger metadata into condition dict for storage
    if trigger.condition:
        condition_to_save = dict(trigger.condition)
        condition_to_save.update({
            "description": trigger.description,
            "category": trigger.category,
            "confidence": trigger.confidence,
            "importance": trigger.importance,
            "related_driver": trigger.related_driver,
            "monitoring_frequency": trigger.monitoring_frequency,
            "status": trigger.status,
            "data_source": trigger.condition.get("data_source", "yahoo_finance_financials"),
        })
        save_trigger_condition(trigger_id, condition_to_save)
    
    trigger_choices = [t.trigger_id for t in triggers]
    return f"✓ Started tracking trigger {trigger_id} for {company}", trigger_rows_with_tracking(triggers, company, ticker), gr.update(choices=trigger_choices, value=trigger_id)


def refresh_trigger_monitor(company_name, state):
    """Refresh the trigger monitor tab with current trigger statuses for a company."""
    if not company_name:
        return "Select a company to view triggers.", [], gr.update(choices=get_all_companies_with_triggers())
    
    from .store import get_all_trigger_conditions, get_trigger_condition
    from .trigger_evaluator import TriggerEvaluator
    from .models import Trigger
    
    # Load trigger conditions from DB
    conditions = get_all_trigger_conditions(company_name)
    if not conditions:
        return f"No triggers found for {company_name}. Run research first.", [], gr.update(choices=get_all_companies_with_triggers())
    
    # Get ticker and other info from state if available, or from first condition
    ticker = state.get("ticker", "") if state else ""
    thesis = state.get("thesis") if state else None
    competitors = thesis.competitors if thesis and hasattr(thesis, 'competitors') else []
    industry = thesis.industry if thesis and hasattr(thesis, 'industry') else ""
    
    # If we don't have thesis in state, we need to reconstruct minimal info
    # For now, we'll use the state if available
    if not ticker and state:
        ticker = state.get("ticker", "")
    
    evaluator = TriggerEvaluator()
    
    # Reconstruct Trigger objects from conditions
    triggers = []
    for cond in conditions:
        trigger_id = cond.get("trigger_id", "")
        # Include main company in related_companies for tracking
        related_companies = ", ".join([company_name] + competitors)
        trigger = Trigger(
            trigger_id=trigger_id,
            category=cond.get("category", ""),
            description=cond.get("description", ""),
            confidence=cond.get("confidence", 0),
            importance=cond.get("importance", "Medium"),
            related_driver=cond.get("related_driver", ""),
            related_companies=related_companies,
            related_industry=industry,
            monitoring_frequency=cond.get("monitoring_frequency", "Daily"),
            status=cond.get("status", "Monitoring"),
            condition=cond,
        )
        triggers.append(trigger)
    
    results = evaluator.evaluate_all_triggers(triggers, company_name, ticker, competitors, industry)
    
    rows = []
    for trigger, eval_result in zip(triggers, results):
        freq = trigger.monitoring_frequency
        next_check = "Manual"
        if freq == "Hours":
            next_check = "~1 hour"
        elif freq == "Daily":
            next_check = "Next 6:00 AM UTC"
        elif freq == "Weekly":
            next_check = "Next Monday 6:00 AM UTC"
        elif freq == "Monthly":
            next_check = "1st of next month 6:00 AM UTC"
        
        condition_str = ""
        if trigger.condition:
            cond = trigger.condition
            if cond.get("condition_type") == "financial_metric":
                condition_str = f"{cond.get('metric_name')} {cond.get('operator')} {cond.get('threshold')} {cond.get('unit')} (lookback: {cond.get('lookback_periods')} {cond.get('period_type')})"
            elif cond.get("condition_type") == "news_keyword":
                condition_str = f"Keywords: {', '.join(cond.get('keywords', []))} in last {cond.get('lookback_periods')} days"
            elif cond.get("condition_type") == "news_sentiment":
                condition_str = f"Sentiment {cond.get('sentiment_threshold')} for {cond.get('threshold')} headlines in {cond.get('lookback_periods')} days"
            elif cond.get("condition_type") == "news_volume":
                condition_str = f"Volume > {cond.get('volume_multiplier')}x baseline ({cond.get('lookback_periods')} days)"
            elif cond.get("condition_type") == "price_change":
                condition_str = f"Price change {cond.get('operator')} {cond.get('threshold')}%"
        
        rows.append([
            trigger.trigger_id,
            trigger.category,
            trigger.description[:80] + "..." if len(trigger.description) > 80 else trigger.description,
            trigger.importance,
            trigger.monitoring_frequency,
            trigger.status,
            condition_str,
            eval_result.details,
            next_check,
        ])
    
    status_md = f"**{len(triggers)} triggers for {company_name}** • Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    companies = get_all_companies_with_triggers()
    return status_md, rows, gr.update(choices=companies, value=company_name)


from datetime import datetime, timezone


with gr.Blocks(title="Signal — AI Investment Intelligence", theme=gr.themes.Soft(primary_hue="indigo")) as demo:
    state = gr.State({})
    gr.Markdown("# Signal\n### AI investment intelligence that tracks what must go right — and what could break the thesis.")
    with gr.Row():
        company = gr.Textbox(label="Company", placeholder="Amazon", scale=3)
        ticker = gr.Textbox(label="Ticker (optional)", placeholder="AMZN", scale=1)
        start = gr.Button("Research company", variant="primary", scale=1)
    research_status = gr.Markdown("Enter a company to start a source-aware investment research workspace.")
    with gr.Tabs():
        with gr.Tab("Investment thesis"):
            thesis_out = gr.Markdown("Research will appear here.")
            profile_out = gr.Markdown()
        with gr.Tab("Financial analysis"):
            gr.Markdown("Income statement, balance sheet, and cash flow metrics across TTM and the last four fiscal years.")
            financial_out = gr.Markdown("Run company research to load financial statements.")
        with gr.Tab("Drivers & triggers"):
            gr.Markdown("### Thesis drivers")
            drivers_out = gr.Dataframe(headers=["Driver", "Description", "Importance", "Direction", "Monitoring", "Source type"], interactive=False)
            gr.Markdown("### Auto-generated triggers")
            triggers_out = gr.Dataframe(
                headers=["ID", "Company", "Ticker", "Category", "Description", "Confidence", "Importance", "Related driver", "Frequency", "Status", "Tracking"],
                interactive=False,
                wrap=True
            )
            with gr.Row():
                track_trigger_dropdown = gr.Dropdown(label="Select trigger to track", choices=[], interactive=True, scale=3)
                track_trigger_btn = gr.Button("Start Tracking", variant="primary", scale=1)
            track_status = gr.Markdown("")
        with gr.Tab("Evaluate new event"):
            event = gr.Textbox(label="New event", lines=7, placeholder="Paste a headline, company announcement, earnings comment, or regulatory development.")
            assess = gr.Button("Evaluate against thesis", variant="primary")
            event_out = gr.Markdown()
        with gr.Tab("Trigger monitor"):
            gr.Markdown("Automated per-trigger monitoring with configurable frequencies. Each trigger evaluates its condition against live data sources on schedule.")
            with gr.Row():
                monitor_company = gr.Dropdown(label="Company", choices=get_all_companies_with_triggers(), interactive=True, allow_custom_value=False, scale=3)
                refresh_btn = gr.Button("Refresh trigger status", variant="primary", scale=1)
            trigger_monitor_status = gr.Markdown("Select a company to view its triggers.")
            trigger_monitor_table = gr.Dataframe(
                headers=["ID", "Category", "Description", "Importance", "Frequency", "Status", "Condition", "Last Evaluation", "Next Check"],
                interactive=False,
                wrap=True
            )
    gr.Markdown("---\n*Decision support only. Verify primary sources before making investment decisions.*")
    start.click(research, [company, ticker], [thesis_out, profile_out, financial_out, drivers_out, triggers_out, state, research_status, track_trigger_dropdown])
    assess.click(assess_event, [event, state], [event_out, triggers_out, state])
    track_trigger_btn.click(start_tracking_trigger, [track_trigger_dropdown, state], [track_status, triggers_out, track_trigger_dropdown])
    refresh_btn.click(refresh_trigger_monitor, [monitor_company, state], [trigger_monitor_status, trigger_monitor_table, monitor_company])
    monitor_company.change(refresh_trigger_monitor, [monitor_company, state], [trigger_monitor_status, trigger_monitor_table, monitor_company])


if __name__ == "__main__":
    demo.launch(server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")))
