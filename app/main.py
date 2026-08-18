import os
import gradio as gr
from .agents import assessment_markdown, collect_full_research, findings_rows, run_live_agents
from .analyst import build_thesis, company_snapshot, drivers_rows, evaluate_event, generate_triggers, summarize_thesis, trigger_rows
from .financial_agent import financial_markdown
from .llm import llm_is_configured
from .notifications import email_is_configured, notify_trigger_changes, send_research_report
from .store import log_event, save_thesis, thesis_history


COMPANY_TICKERS = {"vodafone idea": "IDEA.NS"}


def research(company, ticker):
    if not company or not company.strip():
        raise gr.Error("Enter a publicly traded company to begin research.")
    ticker = ticker.strip() or COMPANY_TICKERS.get(company.strip().lower(), "")
    bundle = collect_full_research(company, ticker)
    print("########################################################")
    print("Bundle:")
    print(bundle)
    print("########################################################")
    research_data = bundle["research"]
    findings = bundle["findings"]
    thesis = build_thesis(company, ticker, research_data, findings)
    print(thesis)
    triggers = generate_triggers(thesis, findings)
    summary = summarize_thesis(thesis)
    version = save_thesis(thesis.company, summary)
    profile = company_snapshot(thesis, research_data)
    # competitors = competitors
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
        f"{len(triggers)} LLM-generated triggers monitoring. {llm_note}"
        f"Research email: {email_result}. "
    )
    return (
        summary,
        profile_md,
        financial_markdown(research_data.get("financials") or {}),
        drivers_rows(thesis),
        trigger_rows(triggers),
        {"thesis": thesis, "triggers": triggers, "ticker": research_data.get("ticker") or ticker, "research": research_data, "findings": findings},
        status,
        thesis_history(thesis.company),
    )


def assess_event(event, state):
    if not state or "thesis" not in state:
        raise gr.Error("Run company research first.")
    if not event or not event.strip():
        raise gr.Error("Paste an event, filing update, headline, or earnings note.")
    thesis, triggers = state["thesis"], state["triggers"]
    before = {trigger.trigger_id: trigger.status for trigger in triggers}
    result, activated = evaluate_event(event, thesis, triggers)
    for trigger in activated:
        trigger.status = "Activated" if result["impact"] == "Negative" else "Strengthened"
    log_event(thesis.company, event, result)
    deliveries = notify_trigger_changes(thesis.company, before, triggers, event, result)
    delivery_note = "No trigger status changed; no email required." if not deliveries else "Email delivery: " + "; ".join(deliveries)
    md = f"## {result['outcome']}\n\n**Impact:** {result['impact']}  \n**Confidence:** {result['confidence']}/100  \n**Evaluated:** {result['evaluated_at']}\n\n**Recommendation:** {result['recommendation']}\n\n**{delivery_note}**\n\n**Evidence note:** {result['evidence']}"
    return md, trigger_rows(triggers), state


def refresh_live_agents(state):
    if not state or "thesis" not in state:
        return "Run company research before starting the live agent monitor.", [], gr.skip(), state, "Live monitor is waiting for a company."
    thesis, triggers = state["thesis"], state["triggers"]
    before = {trigger.trigger_id: trigger.status for trigger in triggers}
    result = run_live_agents(thesis, state.get("ticker", ""), triggers)
    state["live_scan"] = result
    assessment = result["assessment"]
    log_event(thesis.company, "Live multi-agent scan", assessment)
    evidence = "\n".join(item["finding"] for item in result["findings"] if item["impact"] in ("Positive", "Negative"))
    deliveries = notify_trigger_changes(thesis.company, before, triggers, evidence or "Live multi-agent scan", assessment)
    alert_status = "No trigger changes." if not deliveries else "; ".join(deliveries)
    email_status = "Email alerts are configured." if email_is_configured() else "Email alerts are not configured; set the SMTP values in .env."
    llm_note = "LLM analyst active." if llm_is_configured() else "Keyword fallback analyst (set OPENAI_API_KEY for LLM)."
    status = f"Live scan completed at {result['checked_at']} • {assessment['live_sources']} source findings analyzed. {alert_status} {email_status} {llm_note}"
    return assessment_markdown(result), findings_rows(result["findings"]), trigger_rows(triggers), state, status


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
            triggers_out = gr.Dataframe(headers=["ID", "Category", "Description", "Confidence", "Importance", "Related driver", "Frequency", "Status"], interactive=False, wrap=True)
        with gr.Tab("Evaluate new event"):
            event = gr.Textbox(label="New event", lines=7, placeholder="Paste a headline, company announcement, earnings comment, or regulatory development.")
            assess = gr.Button("Evaluate against thesis", variant="primary")
            event_out = gr.Markdown()
        with gr.Tab("Live agent monitor"):
            gr.Markdown("Five independent data agents collect current market, financial, company news, competitor, and policy signals. The LLM analyst agent then evaluates the combined evidence against your thesis and triggers.")
            live_scan = gr.Button("Run live agent scan", variant="primary")
            live_status = gr.Markdown("No live scan has run yet. Configure OPENAI_API_KEY and SMTP values in `.env` for LLM analysis and email alerts.")
            live_assessment = gr.Markdown()
            live_findings = gr.Dataframe(headers=["Agent", "Status", "Impact", "Finding", "Source", "Observed (UTC)"], interactive=False, wrap=True)
        with gr.Tab("Thesis history"):
            history_out = gr.Dataframe(headers=["Version", "Change reason", "Created", "Thesis snapshot"], interactive=False)
    gr.Markdown("---\n*Decision support only. Verify primary sources before making investment decisions.*")
    start.click(research, [company, ticker], [thesis_out, profile_out, financial_out, drivers_out, triggers_out, state, research_status, history_out])
    assess.click(assess_event, [event, state], [event_out, triggers_out, state])
    live_scan.click(refresh_live_agents, [state], [live_assessment, live_findings, triggers_out, state, live_status])


if __name__ == "__main__":
    demo.launch(server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")))
