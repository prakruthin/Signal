"""Live research agents with transparent sources and safe offline fallbacks."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import quote_plus

import requests

from .models import Thesis, Trigger


USER_AGENT = "SignalInvestmentIntelligence/1.0 (research dashboard)"


@dataclass
class AgentFinding:
    agent: str
    status: str
    observed_at: str
    finding: str
    source: str
    url: str = ""
    impact: str = "Unclear"

    def row(self) -> List[str]:
        return [self.agent, self.status, self.impact, self.finding, self.source, self.observed_at]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _request(url: str, params: Dict[str, str] | None = None) -> requests.Response:
    return requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)


def _impact(text: str) -> str:
    lower = text.lower()
    negative = ("fall", "loss", "debt", "delay", "cut", "penalty", "downgrade", "risk", "probe")
    positive = ("gain", "growth", "funding", "profit", "rise", "approval", "upgrade", "partnership", "launch")
    return "Negative" if any(term in lower for term in negative) else "Positive" if any(term in lower for term in positive) else "Unclear"


def _rss_items(url: str, limit: int) -> List[Dict[str, str]]:
    """Fetch and parse the first `limit` items from an RSS feed."""
    response = _request(url)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return [
        {"title": (item.findtext("title") or "Untitled update").strip(), "link": (item.findtext("link") or "").strip()}
        for item in root.findall("./channel/item")[:limit]
    ]


def _price_history(ticker: str) -> Dict[str, Any]:
    """Fetch ~1 year of daily bars and derive range, trend, and volume statistics."""
    response = _request(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_plus(ticker)}",
        {"range": "1y", "interval": "1d"},
    )
    response.raise_for_status()
    payload = response.json()["chart"]["result"][0]
    timestamps = payload.get("timestamp") or []
    quote = (payload.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    points = [(ts, c, v) for ts, c, v in zip(timestamps, closes, volumes) if c is not None]
    if len(points) < 2:
        return {}
    dates = [datetime.fromtimestamp(ts, timezone.utc) for ts, _, _ in points]
    closes = [c for _, c, _ in points]
    volumes = [v or 0 for _, _, v in points]

    def pct_change(start: float, end: float) -> float:
        return (end - start) / start * 100 if start else 0.0

    latest = closes[-1]

    def lookback(days: int) -> float:
        return closes[-days] if len(closes) >= days else closes[0]

    year = datetime.now(timezone.utc).year
    ytd_closes = [c for ts, c, _ in points if datetime.fromtimestamp(ts, timezone.utc).year == year]
    recent_volumes = volumes[-63:]
    return {
        "first_date": dates[0].strftime("%Y-%m-%d"),
        "last_date": dates[-1].strftime("%Y-%m-%d"),
        "high_52w": max(closes),
        "low_52w": min(closes),
        "avg_volume_3m": round(sum(recent_volumes) / len(recent_volumes)) if recent_volumes else 0,
        "change_1m_pct": round(pct_change(lookback(22), latest), 2),
        "change_3m_pct": round(pct_change(lookback(64), latest), 2),
        "change_6m_pct": round(pct_change(lookback(126), latest), 2),
        "change_1y_pct": round(pct_change(closes[0], latest), 2),
        "ytd_change_pct": round(pct_change(ytd_closes[0], latest), 2) if ytd_closes else None,
    }


def _wikipedia_summary(company: str) -> Dict[str, str]:
    """Best-effort company overview from Wikipedia's API (no API key required)."""
    response = _request(
        "https://en.wikipedia.org/w/api.php",
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "titles": company,
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "redirects": "1",
        },
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    if not pages:
        return {}
    page = pages[0]
    extract = (page.get("extract") or "").strip()
    if page.get("missing") or not extract:
        return {}
    return {"title": page.get("title", company), "summary": extract[:1500]}


def _yahoo_rss_headlines(ticker: str, limit: int = 5) -> List[Dict[str, str]]:
    """Headlines for a ticker from Yahoo Finance's RSS feed."""
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(ticker)}&region=US&lang=en-US"
    return [
        {"title": item["title"], "source": "Yahoo Finance RSS", "url": item["link"], "impact": _impact(item["title"])}
        for item in _rss_items(url, limit)
    ]


def _market_snapshot(ticker: str) -> Dict[str, Any]:
    if not ticker:
        return {}
    response = _request(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_plus(ticker)}", {"range": "5d", "interval": "1d"})
    response.raise_for_status()
    meta = response.json()["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice")
    previous = meta.get("chartPreviousClose") or meta.get("previousClose")
    if price is None:
        return {}
    return {"price": price, "previous_close": previous, "change_percent": ((price - previous) / previous * 100) if previous else None, "currency": meta.get("currency")}


class CompanyResearchAgent:
    """Resolves a company and gathers only current, source-attributed research evidence."""

    name = "Company Research Agent"

    def collect(self, company: str, ticker: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {"company": company.strip(), "ticker": ticker.strip().upper(), "name": company.strip(), "industry": "", "exchange": "", "headlines": [], "competitors": [], "market": {}, "history": {}, "summary": "", "sources": [], "source_statuses": []}
        try:
            response = _request("https://query1.finance.yahoo.com/v1/finance/search", {"q": ticker or company, "quotesCount": "8", "newsCount": "0"})
            response.raise_for_status()
            quotes = response.json().get("quotes", [])
            exact = next((q for q in quotes if ticker and q.get("symbol", "").upper() == ticker.upper()), None)
            quote = exact or next((q for q in quotes if q.get("quoteType") in ("EQUITY", "MUTUALFUND", "ETF")), quotes[0] if quotes else {})
            if quote:
                result.update({"ticker": quote.get("symbol") or result["ticker"], "name": quote.get("longname") or quote.get("shortname") or result["name"], "exchange": quote.get("exchange") or quote.get("exchDisp") or "", "industry": quote.get("industry") or quote.get("sector") or ""})
            result["sources"].append("Yahoo Finance search")
            result["source_statuses"].append("Live")
        except Exception:
            result["source_statuses"].append("Unavailable")
        if result["ticker"]:
            try:
                result["market"] = _market_snapshot(result["ticker"])
                result["sources"].append("Yahoo Finance chart API")
                result["source_statuses"].append("Live")
            except Exception:
                result["source_statuses"].append("Unavailable")
            try:
                result["history"] = _price_history(result["ticker"])
                if result["history"]:
                    result["sources"].append("Yahoo Finance 1-year history")
                    result["source_statuses"].append("Live")
                else:
                    result["source_statuses"].append("Unavailable")
            except Exception:
                result["source_statuses"].append("Unavailable")
        try:
            wiki = _wikipedia_summary(result["name"])
            if wiki:
                result["summary"] = wiki["summary"]
                result["sources"].append("Wikipedia")
                result["source_statuses"].append("Live")
            else:
                result["source_statuses"].append("Unavailable")
        except Exception:
            result["source_statuses"].append("Unavailable")
        findings = NewsAgent().collect(result["name"])
        result["source_statuses"].append("Live" if any(f.status == "Live" for f in findings) else "Unavailable")
        result["sources"].append("Google News RSS")
        headlines = [{"title": finding.finding, "source": finding.source, "url": finding.url, "impact": finding.impact} for finding in findings if finding.status == "Live"]
        if result["ticker"]:
            try:
                rss_headlines = _yahoo_rss_headlines(result["ticker"])
                if rss_headlines:
                    headlines.extend(rss_headlines)
                    result["sources"].append("Yahoo Finance RSS")
                    result["source_statuses"].append("Live")
                else:
                    result["source_statuses"].append("Unavailable")
            except Exception:
                result["source_statuses"].append("Unavailable")
        result["headlines"] = headlines
        return result


def collect_full_research(company: str, ticker: str = "") -> Dict[str, Any]:
    """Run all live collectors for initial thesis building."""
    from .financial_agent import FinancialAgent
    from .llm import discover_competitors

    research = CompanyResearchAgent().collect(company, ticker)
    resolved_ticker = research.get("ticker") or ticker
    findings: List[AgentFinding] = []
    findings.extend(MarketDataAgent().collect(resolved_ticker))
    financial_snapshot, financial_findings = FinancialAgent().collect(resolved_ticker, research.get("name") or company)
    research["financials"] = financial_snapshot.to_dict()
    findings.extend(financial_findings)
    findings.extend(NewsAgent().collect(research["name"]))
    if not research.get("competitors") and research.get("industry"):
        research["competitors"] = discover_competitors(research["name"], research["industry"], resolved_ticker)
    competitor_names = [
        c["company"]
        for c in research.get("competitors", [])
        if isinstance(c, dict) and c.get("company")
    ]

    findings.extend(
        CompetitorAgent().collect(
            competitor_names,
            research.get("industry", "")
        )
    )
    # findings.extend(CompetitorAgent().collect(research.get("competitors", []), research.get("industry", "")))
    findings.extend(RegulatoryAgent().collect(research["name"], research.get("industry", "")))
    # print("########################################################")
    # print("Findings:")
    # print(findings)
    # print("########################################################")
    return {"research": research, "findings": [f.to_dict() for f in findings]}


class MarketDataAgent:
    name = "Market Data Agent"

    def collect(self, ticker: str) -> List[AgentFinding]:
        if not ticker or ticker == "—":
            return [AgentFinding(self.name, "Skipped", _now(), "No ticker is configured for this company.", "Yahoo Finance")]
        try:
            snapshot = _market_snapshot(ticker)
            if not snapshot:
                raise ValueError("No market price returned")
            price, change = snapshot["price"], snapshot.get("change_percent") or 0
            impact = "Positive" if change > 2 else "Negative" if change < -2 else "Neutral"
            return [AgentFinding(self.name, "Live", _now(), f"{ticker}: {price:,.2f} ({change:+.2f}% versus prior close).", "Yahoo Finance chart API", f"https://finance.yahoo.com/quote/{ticker}", impact)]
        except Exception as exc:
            return [AgentFinding(self.name, "Unavailable", _now(), f"Live quote could not be retrieved ({type(exc).__name__}).", "Yahoo Finance", impact="Unclear")]


class NewsAgent:
    name = "Company News Agent"

    def collect(self, company: str) -> List[AgentFinding]:
        query = quote_plus(f'"{company}" stock')
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        try:
            items = _rss_items(url, 10)
            if not items:
                return [AgentFinding(self.name, "Live", _now(), "No recent matching headlines found.", "Google News RSS")]
            return [AgentFinding(self.name, "Live", _now(), item["title"], "Google News RSS", item["link"], _impact(item["title"])) for item in items]
        except Exception as exc:
            return [AgentFinding(self.name, "Unavailable", _now(), f"Live news could not be retrieved ({type(exc).__name__}).", "Google News RSS")]


class CompetitorAgent:
    name = "Competitor Intelligence Agent"

    def collect(self, competitors: List[str], industry: str) -> List[AgentFinding]:
        if not competitors:
            return [AgentFinding(self.name, "Skipped", _now(), "No competitors were returned by the live research sources.", "Dynamic research")]
        query = quote_plus(" OR ".join(f'"{c}"' for c in competitors) + f" {industry}")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        try:
            items = _rss_items(url, 4)
            if not items:
                return [AgentFinding(self.name, "Live", _now(), "No recent competitor developments found.", "Google News RSS")]
            return [AgentFinding(self.name, "Live", _now(), item["title"], "Google News RSS", item["link"], _impact(item["title"])) for item in items]
        except Exception as exc:
            return [AgentFinding(self.name, "Unavailable", _now(), f"Competitor scan could not be retrieved ({type(exc).__name__}).", "Google News RSS")]


class RegulatoryAgent:
    name = "Regulatory & Policy Agent"

    def collect(self, company: str, industry: str) -> List[AgentFinding]:
        query = quote_plus(f'"{company}" {industry} regulation policy')
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        try:
            items = _rss_items(url, 3)
            if not items:
                return [AgentFinding(self.name, "Live", _now(), "No recent policy developments found.", "Google News RSS")]
            return [AgentFinding(self.name, "Live", _now(), item["title"], "Google News RSS", item["link"], _impact(item["title"])) for item in items]
        except Exception as exc:
            return [AgentFinding(self.name, "Unavailable", _now(), f"Policy scan could not be retrieved ({type(exc).__name__}).", "Google News RSS")]


class InvestmentAnalystAgent:
    name = "Investment Analyst Agent"

    def analyze(self, findings: List[AgentFinding], thesis: Thesis, triggers: List[Trigger]) -> Dict[str, Any]:
        from .llm import assess_findings_with_llm

        finding_dicts = [f.to_dict() for f in findings]
        llm_result = assess_findings_with_llm(finding_dicts, thesis, triggers)
        if llm_result:
            return llm_result

        from .analyst import evaluate_event

        live = [f for f in findings if f.status == "Live"]
        positives = sum(f.impact == "Positive" for f in live)
        negatives = sum(f.impact == "Negative" for f in live)
        material = [f for f in live if f.impact in ("Positive", "Negative")]
        combined_text = " ".join(f.finding for f in material)
        evaluation, matches = evaluate_event(combined_text, thesis, triggers) if combined_text else ({"outcome": "No material live signal", "impact": "Unclear", "confidence": 50, "recommendation": "Continue monitoring.", "evidence": "No classified live signals were returned."}, [])
        if positives > negatives:
            stance = "Improving"
        elif negatives > positives:
            stance = "Deteriorating"
        else:
            stance = "Stable / mixed"
        evaluation.update({"agent": self.name, "stance": stance, "live_sources": len(live), "positive_signals": positives, "negative_signals": negatives, "matched_trigger_ids": [x.trigger_id for x in matches]})
        return evaluation


def run_live_agents(thesis: Thesis, ticker: str, triggers: List[Trigger]) -> Dict[str, Any]:
    """Run independent collectors, then pass their evidence to the analyst agent."""
    from .financial_agent import FinancialAgent

    findings = []
    findings.extend(MarketDataAgent().collect(ticker))
    _, financial_findings = FinancialAgent().collect(ticker, thesis.company)
    findings.extend(financial_findings)
    findings.extend(NewsAgent().collect(thesis.company))
    findings.extend(CompetitorAgent().collect(thesis.competitors, thesis.industry))
    findings.extend(RegulatoryAgent().collect(thesis.company, thesis.industry))
    assessment = InvestmentAnalystAgent().analyze(findings, thesis, triggers)
    for trigger in triggers:
        if trigger.trigger_id in assessment["matched_trigger_ids"]:
            trigger.status = "Activated" if assessment["impact"] == "Negative" else "Strengthened"
    return {"findings": [f.to_dict() for f in findings], "assessment": assessment, "checked_at": _now()}


def findings_rows(findings: List[Dict[str, Any]]) -> List[List[str]]:
    return [[f["agent"], f["status"], f["impact"], f["finding"], f["source"], f["observed_at"]] for f in findings]


def assessment_markdown(result: Dict[str, Any]) -> str:
    assessment = result["assessment"]
    return (
        f"## Dynamic assessment: {assessment['stance']}\n\n"
        f"**Thesis impact:** {assessment['impact']}  \n"
        f"**Analyst confidence:** {assessment['confidence']}/100  \n"
        f"**Live source findings:** {assessment['live_sources']} • **Positive:** {assessment['positive_signals']} • **Negative:** {assessment['negative_signals']}  \n"
        f"**Checked:** {result['checked_at']}\n\n"
        f"**Outcome:** {assessment['outcome']}  \n\n"
        f"**Recommendation:** {assessment['recommendation']}\n\n"
        f"*Evidence note: {assessment['evidence']}*"
    )
