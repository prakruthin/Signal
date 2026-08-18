import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .models import Driver, Thesis, Trigger, ThesisPoint


POSITIVE_TERMS = ("gain", "growth", "profit", "approval", "funding", "rise", "upgrade", "partnership", "launch", "award")
NEGATIVE_TERMS = ("loss", "decline", "fall", "debt", "delay", "penalty", "downgrade", "cut", "risk", "probe")


def _headline_signal(headline: str) -> int:
    words = headline.lower()
    return sum(word in words for word in POSITIVE_TERMS) - sum(word in words for word in NEGATIVE_TERMS)


def _driver_title(headline: str) -> str:
    cleaned = re.sub(r"\s+-\s+[^-]+$", "", headline).strip()
    return cleaned[:110] + ("…" if len(cleaned) > 110 else "")


def build_thesis(
    company: str,
    ticker: str = "",
    research: Dict[str, Any] | None = None,
    findings: List[Dict[str, Any]] | None = None,
) -> Thesis:
    """Create every thesis field from current research-agent data, never from a profile."""
    from .llm import build_thesis_with_llm

    research = research or {"company": company, "ticker": ticker, "headlines": [], "source_statuses": []}
    llm_thesis = build_thesis_with_llm(research, findings or [])
    if llm_thesis:
        return llm_thesis
    name = research.get("name") or company.strip()
    competitors = research.get("competitors") or []
    industry = research.get("industry") or "Unclassified by current live sources"
    headlines = research.get("headlines", [])
    live_sources = sum(status == "Live" for status in research.get("source_statuses", []))
    market = research.get("market") or {}
    history = research.get("history") or {}
    scored = [(item, _headline_signal(item.get("title", ""))) for item in headlines]
    positive = [item for item, score in scored if score > 0]
    negative = [item for item, score in scored if score < 0]

    from .financial_agent import financial_thesis_signals

    financial_signals = financial_thesis_signals(research.get("financials") or {})
    print("########################################################")
    print("Financial signals:")
    print(financial_signals)
    print("########################################################")

    bull_points: List[ThesisPoint] = []
    for point in financial_signals.get("bull", [])[:3]:
        bull_points.append(ThesisPoint(
            factor="Financial Strength",
            explanation=point,
            evidence=f"From financial statements: {point}",
            importance="High"
        ))
    for item in positive[:3]:
        title = _driver_title(item.get("title", "Live news event"))
        bull_points.append(ThesisPoint(
            factor="Positive News Catalyst",
            explanation=f"Recent positive development: {title}",
            evidence=f"Source: {item.get('source', 'Live news')}. Headline: {item.get('title', '')}",
            importance="Medium"
        ))
    if market.get("change_percent") is not None and market["change_percent"] >= 0:
        bull_points.append(ThesisPoint(
            factor="Positive Market Momentum",
            explanation=f"Stock showing positive price action versus prior close",
            evidence=f"Market data: {market['change_percent']:+.2f}% change vs prior close",
            importance="Medium"
        ))
    if history.get("change_1y_pct") is not None and history["change_1y_pct"] >= 0:
        bull_points.append(ThesisPoint(
            factor="Positive Long-term Performance",
            explanation=f"Stock has delivered positive returns over the past year",
            evidence=f"52-week range: {history['low_52w']:,.2f} – {history['high_52w']:,.2f}; 1-year change: {history['change_1y_pct']:+.2f}%",
            importance="Medium"
        ))
    if not bull_points:
        bull_points.append(ThesisPoint(
            factor="Insufficient Positive Evidence",
            explanation="No clearly positive live signal was classified in the current research scan.",
            evidence="Research scan returned no usable positive findings.",
            importance="Low"
        ))

    bear_points: List[ThesisPoint] = []
    for point in financial_signals.get("bear", [])[:3]:
        bear_points.append(ThesisPoint(
            factor="Financial Risk",
            explanation=point,
            evidence=f"From financial statements: {point}",
            importance="High"
        ))
    for item in negative[:3]:
        title = _driver_title(item.get("title", "Live news event"))
        bear_points.append(ThesisPoint(
            factor="Negative News Catalyst",
            explanation=f"Recent negative development: {title}",
            evidence=f"Source: {item.get('source', 'Live news')}. Headline: {item.get('title', '')}",
            importance="Medium"
        ))
    if market.get("change_percent") is not None and market["change_percent"] < 0:
        bear_points.append(ThesisPoint(
            factor="Negative Market Momentum",
            explanation=f"Stock showing negative price action versus prior close",
            evidence=f"Market data: {market['change_percent']:+.2f}% change vs prior close",
            importance="Medium"
        ))
    if history.get("change_1y_pct") is not None and history["change_1y_pct"] < 0:
        bear_points.append(ThesisPoint(
            factor="Negative Long-term Performance",
            explanation=f"Stock has delivered negative returns over the past year",
            evidence=f"52-week range: {history['low_52w']:,.2f} – {history['high_52w']:,.2f}; 1-year change: {history['change_1y_pct']:+.2f}%",
            importance="Medium"
        ))
    if not bear_points:
        bear_points.append(ThesisPoint(
            factor="Insufficient Negative Evidence",
            explanation="No clearly negative live signal was classified in the current research scan.",
            evidence="Research scan returned no usable negative findings.",
            importance="Low"
        ))

    drivers: List[Driver] = []
    for item in financial_signals.get("drivers", []):
        drivers.append(
            Driver(
                str(item.get("name", "Financial metric")),
                str(item.get("description", "")),
                int(item.get("importance", 7)),
                str(item.get("direction", "Neutral")),
                True,
                str(item.get("source_type", "Financial statements")),
            )
        )
    if market.get("price") is not None:
        direction = "Positive" if market.get("change_percent", 0) >= 0 else "Negative"
        drivers.append(Driver("Observed market response", f"Live price: {market['price']:,.2f}; change: {market.get('change_percent', 0):+.2f}% versus prior close.", 6, direction, True, "Market data"))
    if history:
        direction = "Positive" if (history.get("change_1y_pct") or 0) >= 0 else "Negative"
        drivers.append(Driver("52-week performance", f"Past-year range: {history['low_52w']:,.2f} – {history['high_52w']:,.2f}; 1-year move {history.get('change_1y_pct', 0):+.2f}%.", 5, direction, True, "Historical market data"))
    for item, signal in scored[:5]:
        direction = "Positive" if signal > 0 else "Negative" if signal < 0 else "Neutral"
        drivers.append(Driver(_driver_title(item.get("title", "Live news event")), "A current source-reported event to verify and monitor. " + item.get("source", ""), 9 if direction == "Negative" else 7, direction, True, "Live news"))
    if not drivers:
        drivers.append(Driver("Research coverage", "No usable live evidence was returned. Re-run the research agents when data sources are reachable.", 10, "Negative", True, "Source health"))

    evidence_points = len(headlines) + (1 if market.get("price") is not None else 0) + (1 if history else 0)
    if financial_signals.get("available"):
        evidence_points += len(financial_signals.get("bull", [])) + len(financial_signals.get("bear", []))
    balance_penalty = min(12, abs(len(positive) - len(negative)) * 2)
    confidence = max(15, min(90, 20 + live_sources * 12 + evidence_points * 4 - balance_penalty))
    if not financial_signals.get("available"):
        confidence = max(15, confidence - 10)
    financial_note = (
        f" Financial statement signal: {financial_signals.get('impact', 'Unclear')}."
        if financial_signals.get("available")
        else " Financial statements were unavailable; financial quality is unverified."
    )
    base = (
        f"The current thesis is based on {evidence_points} live evidence points from {live_sources} available sources. "
        f"Positive signals: {len(positive) + len(financial_signals.get('bull', []))}; "
        f"negative signals: {len(negative) + len(financial_signals.get('bear', []))}.{financial_note} "
        "The view should change as new source-backed evidence arrives."
    )
    assumptions = [
        "Live-source retrieval is current and accurately attributed.",
        "Headline-level signals require confirmation in primary filings, releases, or transcripts.",
        f"The observed {industry} classification remains valid for this company.",
    ]
    if financial_signals.get("available"):
        assumptions.append("Reported financial statement figures reflect the latest available filings via Yahoo Finance.")
    else:
        assumptions.append("Financial statement analysis was not available; profitability, leverage, and cash flow are unverified.")
    challenge = "This evidence-led thesis is invalidated if primary sources contradict the collected signals or if the live source coverage is incomplete."
    return Thesis(company=name, industry=industry, bull_case=bull_points, bear_case=bear_points, base_case=base, confidence=confidence, assumptions=assumptions, challenge=challenge, drivers=drivers, competitors=competitors)


def company_snapshot(thesis: Thesis, research: Dict[str, Any] | None = None) -> Dict[str, str]:
    research = research or {}
    market = research.get("market") or {}
    history = research.get("history") or {}
    source_list = ", ".join(research.get("sources", [])) or "No live source returned usable company metadata."

    def _number(value: Any, suffix: str = "") -> str:
        return f"{value:,.2f}{suffix}" if isinstance(value, (int, float)) else str(value or "N/A")

    snapshot = {
        "Resolved company": thesis.company,
        "Ticker": research.get("ticker") or "Not resolved",
        "Exchange": research.get("exchange") or "Not returned",
        "Classification": thesis.industry,
        "Latest market observation": f"{_number(market.get('price'))} ({_number(market.get('change_percent'))}% versus prior close)",
        "52-week range": f"{_number(history.get('low_52w'))} – {_number(history.get('high_52w'))}",
        "1-year performance": _number(history.get("change_1y_pct"), "%"),
        "YTD performance": _number(history.get("ytd_change_pct"), "%"),
        "Live sources": source_list,
    }
    if research.get("summary"):
        summary = research["summary"]
        snapshot["Company summary"] = summary[:400] + ("…" if len(summary) > 400 else "")
    return snapshot


def generate_triggers(thesis: Thesis, findings: List[Dict[str, Any]] | None = None) -> List[Trigger]:
    """Generate monitoring rules from live research drivers, not sector/company templates."""
    from .llm import generate_triggers_with_llm

    llm_triggers = generate_triggers_with_llm(thesis, findings or [])
    if llm_triggers:
        return llm_triggers

    output = []
    for driver in thesis.drivers:
        category = "Positive" if driver.direction == "Positive" else "Negative" if driver.direction == "Negative" else "Hold"
        importance = "Critical" if driver.importance >= 9 else "High" if driver.importance >= 7 else "Medium"
        description = f"A source-confirmed material update changes the evidence for: {driver.name}"
        confidence = min(90, max(40, thesis.confidence + (6 if driver.direction != "Neutral" else 0)))
        frequency = "Hours" if driver.importance >= 8 else "Daily"
        raw = f"{thesis.company}:{category}:{description}".encode()
        output.append(Trigger("TRG-" + hashlib.sha1(raw).hexdigest()[:7].upper(), category, description, confidence, importance, driver.name, ", ".join(thesis.competitors), thesis.industry, frequency))
    return output


def evaluate_event(event: str, thesis: Thesis, triggers: List[Trigger]) -> Tuple[Dict, List[Trigger]]:
    from .llm import evaluate_with_llm

    llm_result = evaluate_with_llm(event, thesis, triggers)
    if llm_result:
        return llm_result

    score = _headline_signal(event)
    text = event.lower()
    triggered = [trigger for trigger in triggers if any(token in text for token in re.findall(r"[a-zA-Z]{5,}", trigger.related_driver.lower()))]
    if score > 0:
        outcome, impact, recommendation = "Trigger strengthened" if triggered else "Material positive development", "Positive", "Verify the source and reassess whether thesis confidence should increase."
    elif score < 0:
        outcome, impact, recommendation = "Trigger activated" if triggered else "Material risk development", "Negative", "Verify primary evidence and reassess whether a core assumption has failed."
    else:
        outcome, impact, recommendation = "Needs analyst review", "Unclear", "Confirm source quality and connect the event to a live research driver before acting."
    return {"event": event, "outcome": outcome, "impact": impact, "confidence": min(92, 50 + 8 * abs(score) + (8 if triggered else 0)), "recommendation": recommendation, "evidence": "Assessment derived from the current dynamic trigger set and event text.", "evaluated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}, triggered


def summarize_thesis(t: Thesis) -> str:
    def format_points(points: List[ThesisPoint], label: str) -> str:
        if not points:
            return f"### {label}\nNo {label.lower()} points identified.\n"
        parts = [f"### {label}"]
        for i, p in enumerate(points, 1):
            md = f"\n**{i}. {p.factor}** ({p.importance} importance)\n\n"
            md += f"{p.explanation}\n\n"
            md += f"**Evidence:** {p.evidence}\n"
            if p.additional_evidence:
                md += f"**Additional Evidence:** {p.additional_evidence}\n"
            parts.append(md)
        return "\n".join(parts)

    return (
        f"## {t.company} — Investment Thesis\n\n"
        f"**Industry:** {t.industry}  \n"
        f"**Thesis confidence:** {t.confidence}/100\n\n"
        f"### Base case\n{t.base_case}\n\n"
        f"{format_points(t.bull_case, 'Bull case')}\n\n"
        f"{format_points(t.bear_case, 'Bear case')}\n\n"
        f"### Critical assumptions\n" + "\n".join(f"- {x}" for x in t.assumptions) + 
        f"\n\n### What could prove this wrong?\n{t.challenge}" + 
        f"\n\n### Competitors\n" + "\n".join(f"- {x}" for x in t.competitors)
    )

# def summarize_thesis(t: Thesis) -> str:
#     competitors_text = "\n".join(
#         f"- {c['company']} ({c['ticker']}) | Threat: {c['threat_level']}\n"
#         f"  Reason: {c['reason']}"
#         for c in t.competitors
#     )

#     return (
#         f"## {t.company} — Investment Thesis\n\n"
#         f"**Industry:** {t.industry}  \n"
#         f"**Thesis confidence:** {t.confidence}/100\n\n"
#         f"### Base case\n{t.base_case}\n\n"
#         f"### Bull case\n" + "\n".join(f"- {x}" for x in t.bull_case)
#         + "\n\n### Bear case\n" + "\n".join(f"- {x}" for x in t.bear_case)
#         + "\n\n### Critical assumptions\n" + "\n".join(f"- {x}" for x in t.assumptions)
#         + f"\n\n### What could prove this wrong?\n{t.challenge}"
#         + f"\n\n### Competitors\n{competitors_text}"
#     )

def drivers_rows(thesis: Thesis) -> List[List]:
    return [[d.name, d.description, d.importance, d.direction, "Yes" if d.monitoring_required else "No", d.source_type] for d in thesis.drivers]


def trigger_rows(triggers: List[Trigger]) -> List[List]:
    return [[t.trigger_id, t.category, t.description, t.confidence, t.importance, t.related_driver, t.monitoring_frequency, t.status] for t in triggers]
