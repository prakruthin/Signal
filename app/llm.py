"""LLM-backed analysis for thesis, triggers, and event evaluation."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

from .models import Driver, Thesis, Trigger, ThesisPoint, TriggerCondition

load_dotenv()


def llm_is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


def _client():
    from openai import OpenAI

    kwargs: Dict[str, Any] = {"api_key": os.getenv("OPENAI_API_KEY", "").strip()}
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _chat_json(system: str, user: str) -> Dict[str, Any]:
    response = _client().chat.completions.create(
        model=_model(),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    return _parse_json(content)


def _findings_text(findings: List[Dict[str, Any]]) -> str:
    lines = []
    for item in findings:
        lines.append(
            f"- [{item.get('agent', 'Agent')}] status={item.get('status')} impact={item.get('impact')} "
            f"source={item.get('source')}: {item.get('finding')}"
        )
    return "\n".join(lines) if lines else "No agent findings available."


def _research_text(research: Dict[str, Any]) -> str:
    market = research.get("market") or {}
    history = research.get("history") or {}
    headlines = research.get("headlines") or []
    headline_lines = "\n".join(f"- {h.get('title')} ({h.get('source')}, {h.get('impact')})" for h in headlines[:8])
    summary = research.get("summary") or ""
    summary_line = f"Company summary: {summary[:900]}\n" if summary else ""
    history_line = (
        f"52-week range: {history.get('low_52w')} - {history.get('high_52w')}; "
        f"1-month: {history.get('change_1m_pct')}%, 6-month: {history.get('change_6m_pct')}%, "
        f"1-year: {history.get('change_1y_pct')}%, YTD: {history.get('ytd_change_pct')}%\n"
        if history else ""
    )
    return (
        f"Company: {research.get('name') or research.get('company')}\n"
        f"Ticker: {research.get('ticker') or 'unknown'}\n"
        f"Exchange: {research.get('exchange') or 'unknown'}\n"
        f"Industry: {research.get('industry') or 'unknown'}\n"
        f"Market price: {market.get('price', 'N/A')} ({market.get('change_percent', 'N/A')}% vs prior close)\n"
        f"{history_line}"
        f"{summary_line}"
        f"Competitors: {research.get('competitors') or 'unknown'}\n"
        f"{_financial_text(research.get('financials') or {})}\n"
        f"Headlines:\n{headline_lines or 'none'}"
    )


def _financial_text(financials: Dict[str, Any]) -> str:
    if not financials or financials.get("status") != "Live":
        return "Financials: unavailable."
    perf = financials.get("performance") or {}
    health = financials.get("health") or {}
    cf = financials.get("cash_flow") or {}

    def ttm(metric: Dict[str, Any]) -> str:
        value = metric.get("TTM")
        return "N/A" if value is None else f"{value:,.2f}"

    return (
        "Financials (TTM where noted):\n"
        f"- Revenue: {ttm(perf.get('revenue', {}))}; growth: {ttm(perf.get('revenue_growth', {}))}%\n"
        f"- Gross margin: {ttm(perf.get('gross_margin', {}))}%; operating margin: {ttm(perf.get('operating_margin', {}))}%\n"
        f"- Net income: {ttm(perf.get('net_income', {}))}; EPS: {ttm(perf.get('eps', {}))}\n"
        f"- Cash: {ttm(health.get('cash', {}))}; debt: {ttm(health.get('debt', {}))}; net debt: {ttm(health.get('net_debt', {}))}\n"
        f"- Operating cash flow: {ttm(cf.get('operating_cash_flow', {}))}; FCF: {ttm(cf.get('free_cash_flow', {}))}; FCF margin: {ttm(cf.get('fcf_margin', {}))}%"
    )


def discover_competitors(company: str, industry: str, ticker: str = "") -> List[str]:
    if not llm_is_configured():
        return []
    # data = _chat_json(
    #     "Return JSON with key competitors: array of 3-5 publicly traded competitor company names. "
    #     "Use only well-known peers for the given company and industry. No commentary.",
    #     f"Company: {company}\nTicker: {ticker or 'unknown'}\nIndustry: {industry or 'unknown'}",
    # )
    # data = _chat_json(
    #     """
    #     You are an experienced equity research analyst.

    #     Return JSON with key:
    #     {
    #         "competitors": ["Company A", "Company B"]
    #     }

    #     Rules:
    #     - Return 3-5 direct publicly traded competitors.
    #     - Prefer companies with similar products, services, and customers.
    #     - Prefer competitors operating in the same geography.
    #     - Exclude suppliers, customers, partners, and parent companies.
    #     - Exclude private companies.
    #     - Exclude companies that are only loosely related to the industry.
    #     - Rank competitors from most relevant to least relevant.
    #     - Return only valid JSON with the competitors array.
    #     """,
    #     f"""
    #     Company: {company}
    #     Ticker: {ticker or 'unknown'}
    #     Industry: {industry or 'unknown'}
    #     """,
    # )


    data = _chat_json(
        """
        You are a senior equity research analyst specializing in competitive intelligence. 

        Your task is to identify the most relevant publicly traded competitors for investment analysis.

        Return ONLY valid JSON:

        {
        "competitors": [
            {
            "company": "Company Name",
            "ticker": "Ticker Symbol",
            "reason": "Why this company is a direct competitor",
            "competitive_overlap": "Products/services/customer segments/geography overlap",
            "threat_level": "High|Medium|Low"
            }
        ]
        }

        Rules:

        - Identify 3-5 strongest direct competitors.
        - Prioritize companies competing for the same customers and revenue pools.
        - Consider:
            - Product/service similarity
            - Market positioning
            - Geography
            - Customer segments
            - Pricing competition
            - Technology overlap
            - Scale comparison

        Exclude:
        - Suppliers
        - Customers
        - Distributors
        - Holding companies
        - Private companies
        - Companies with only indirect industry similarity

        Rank competitors from highest competitive threat to lowest.

        The objective is to understand:
        1. Who can take market share?
        2. Who can pressure margins?
        3. Who can disrupt the company's growth?
        4. Who should investors monitor?

        Do not provide commentary outside JSON.
        # """,
        f"Company: {company}\nTicker: {ticker or 'unknown'}\nIndustry: {industry or 'unknown'}",
        )
    # return [str(x).strip() for x in data.get("competitors", []) if str(x).strip()][:5]
    competitors = []

    for comp in data.get("competitors", []):
        if not isinstance(comp, dict):
            continue

        competitors.append(
            {
                "company": str(comp.get("company", "")).strip(),
                "ticker": str(comp.get("ticker", "")).strip(),
                "reason": str(comp.get("reason", "")).strip(),
                "competitive_overlap": str(
                    comp.get("competitive_overlap", "")
                ).strip(),
                "threat_level": str(
                    comp.get("threat_level", "Medium")
                ).strip(),
            }
        )

    return competitors[:5]


def build_thesis_with_llm(research: Dict[str, Any], findings: List[Dict[str, Any]]) -> Thesis | None:
    if not llm_is_configured():
        return None
    
    # system_prompt = """
    #     You are a senior investment analyst with more than 30 years of experience.

    #     Your task is to build an evidence-based investment thesis using ONLY the supplied live research
    #     and agent findings.

    #     Return ONLY valid JSON with these keys:

    #     {
    #     "company": "",
    #     "industry": "",
    #     "bull_case": [],
    #     "bear_case": [],
    #     "base_case": "",
    #     "confidence": 0,
    #     "confidence_explanation": "",
    #     "assumptions": [],
    #     "challenge": "",
    #     "competitors": [],
    #     "drivers": [
    #         {
    #         "name": "",
    #         "description": "",
    #         "importance": 1,
    #         "direction": "Positive|Negative|Neutral",
    #         "monitoring_required": true,
    #         "source_type": ""
    #         }
    #     ]
    #     }

    #     IMPORTANT:

    #     Confidence must measure the QUALITY AND COMPLETENESS OF THE EVIDENCE,
    #     not whether the thesis is bullish or bearish.

    #     Use this confidence framework:

    #     90-100:
    #     Very strong evidence across financial performance, financial health,
    #     cash flow, market data, competition, industry conditions and catalysts.
    #     Multiple independent sources support the major conclusions.
    #     Data is recent and internally consistent.
    #     Very few material unanswered questions remain.

    #     80-89:
    #     Strong evidence across most major investment dimensions.
    #     Some uncertainty remains, but the core thesis is well supported.

    #     70-79:
    #     Good evidence, but one or more important areas are incomplete,
    #     weakly supported, or conflicting.

    #     60-69:
    #     Moderate evidence. Several important gaps or uncertainties exist.

    #     40-59:
    #     Weak or incomplete evidence. Major investment questions remain unanswered.

    #     0-39:
    #     Insufficient evidence to form a reliable investment thesis.

    #     Increase confidence when:
    #     - multiple independent findings support the same conclusion
    #     - financial statements provide measurable trends
    #     - TTM and fiscal-year trends agree
    #     - revenue, profitability and cash-flow trends are internally consistent
    #     - balance-sheet risk is measurable
    #     - market and competitive evidence support the thesis
    #     - important claims are supported by primary or high-quality sources
    #     - recent information confirms older evidence
    #     - there are few unresolved contradictions

    #     Decrease confidence when:
    #     - important information is missing
    #     - financial statements are unavailable
    #     - findings conflict materially
    #     - evidence is stale
    #     - a conclusion depends heavily on assumptions
    #     - valuation cannot be assessed
    #     - competitive position is unclear
    #     - management quality cannot be evaluated
    #     - regulatory or industry risks are unknown

    #     Do NOT increase confidence merely because there are many findings.
    #     Do NOT decrease confidence merely because the company has risks.
    #     A company can have a high-confidence bearish thesis.

    #     Never invent facts.
    #     Every important positive or negative conclusion must reference supplied evidence.
    #     """
    # data = _chat_json(
    #     "You are a senior investment analyst with more than 30 years of experience."
    #     "Your task is to build an evidence-based thesis ONLY from the supplied live research. "
    #     "Return JSON with keys: company, industry, bull_case (string array), bear_case (string array), "
    #     "base_case (string), confidence (integer 0-100), assumptions (string array), challenge (string), "
    #     "competitors (string array), drivers (array of objects with name, description, importance 1-10, "
    #     "direction in Positive|Negative|Neutral, monitoring_required boolean, source_type). "
    #     "Cite specific headlines, market data, and financial statement figures in bull/bear cases. "
    #     "Do not invent facts not in the evidence."
    #     """Investment reasoning rules:

    #     1. Never make a conclusion from a single data point.
    #     2. Weigh multiple factors:
    #     - Revenue growth
    #     - Profitability
    #     - Debt position
    #     - Cash flow
    #     - Market share
    #     - Competitive pressure
    #     - Industry cycle
    #     - Management quality
    #     - Valuation
    #     - Regulatory environment

    #     3. Financial analysis is REQUIRED when provided. You MUST incorporate:
    #     - Financial Performance: revenue, revenue growth, gross/operating/EBITDA margins, net income, EPS, EPS growth (TTM and fiscal years)
    #     - Financial Health: cash, debt, net debt, working capital, debt/equity, debt/assets
    #     - Cash Flow Analysis: operating cash flow, CapEx, free cash flow, FCF margin, FCF growth, FCF conversion
    #     Include at least one bull or bear point grounded in financial statements.
    #     Add at least two drivers sourced from financial metrics (source_type: Financial statements).
    #     Reference TTM vs prior fiscal years when assessing trends.

    #     4. Every positive or negative statement MUST reference supporting evidence.

    #     5. Clearly separate:
    #     - Facts
    #     - Interpretation
    #     - Investment conclusion

    #     6. If financial analysis is unavailable:
    #     - Reduce confidence score
    #     - Mention uncertainty in assumptions
    #     - Do not assume positive or negative financial quality.

    #     7. Think like a professional investor managing risk-adjusted returns.""",
    #     f"Live research snapshot:\n{_research_text(research)}\n\nAgent findings:\n{_findings_text(findings)}",
    # )
    # print("########################################################")
    # print("Data from build_thesis_with_llm:")
    # print(data)
    # print("########################################################")
    
    # data = _chat_json(
    #     """You are a senior portfolio manager and institutional equity research analyst with 25+ years of experience managing public equity investments."""
 
    #     """Your task is to create a professional investment thesis using ONLY the provided research evidence.

    #     Think like an investor deciding whether to:
    #     - Increase exposure
    #     - Maintain position
    #     - Reduce exposure
    #     - Exit investment

        
    #     Return ONLY valid JSON with the following structure:

    #     {
    #     "company": "",
    #     "industry": "",

    #     "investment_rating": {
    #         "rating": "Strong Buy|Buy|Hold|Reduce|Sell",
    #         "score": 0-100,
    #         "justification": ""
    #     },

    #     "investment_summary": "",

    #     "bull_case": [
    #         {
    #         "factor": "",
    #         "evidence": "",
    #         "importance": "High|Medium|Low"
    #         }
    #     ],

    #     "bear_case": [
    #         {
    #         "factor": "",
    #         "evidence": "",
    #         "risk_level": "High|Medium|Low"
    #         }
    #     ],

    #     "base_case": "",

    #     "upside_drivers": [
    #         {
    #         "driver": "",
    #         "expected_impact": "",
    #         "probability": "High|Medium|Low"
    #         }
    #     ],

    #     "downside_risks": [
    #         {
    #         "risk": "",
    #         "potential_damage": "",
    #         "probability": "High|Medium|Low"
    #         }
    #     ],

    #     "financial_quality_assessment": {
    #         "growth": "Strong|Moderate|Weak",
    #         "profitability": "Strong|Moderate|Weak",
    #         "balance_sheet": "Strong|Moderate|Weak",
    #         "cash_flow": "Strong|Moderate|Weak",
    #         "management_quality": "Strong|Moderate|Weak",
    #         "overall_commentary": ""
    #     },

    #     "competitive_position": {
    #         "market_position": "",
    #         "competitive_advantage": "",
    #         "threats": ""
    #     },

    #     "management_assessment": {
    #         "execution_quality": "",
    #         "capital_allocation": "",
    #         "promoter_management_confidence": ""
    #     },

    #     "valuation_view": {
    #         "valuation_status": "Undervalued|Fairly Valued|Overvalued|Unknown",
    #         "reason": "",
    #         "key_metrics_to_monitor": []
    #     },

    #     "confidence": 0-100,

    #     "confidence_explanation": "",

    #     "key_assumptions": [],

    #     "investment_decision": {
    #         "recommended_action": "Increase Exposure|Maintain|Reduce Exposure|Exit",
    #         "reason": ""
    #     },

    #     "drivers": [
    #     {
    #     "name":"",
    #     "description":"",
    #     "importance":1-10,
    #     "direction":"Positive|Negative|Neutral",
    #     "monitoring_required":true,
    #     "source_type":""
    #     }
    #     ],

    #     "competitors":[]
    #     },


    #     Investment reasoning rules:

    #     1. Never make a conclusion from a single data point.
    #     2. Weigh multiple factors:
    #     - Revenue growth
    #     - Profitability
    #     - Debt position
    #     - Cash flow
    #     - Market share
    #     - Competitive pressure
    #     - Industry cycle
    #     - Management quality
    #     - Valuation
    #     - Regulatory environment

    #     3. Every positive or negative statement MUST reference supporting evidence.

    #     4. Clearly separate:
    #     - Facts
    #     - Interpretation
    #     - Investment conclusion

    #     5. If information is missing:
    #     - Reduce confidence score
    #     - Mention uncertainty
    #     - Do not assume positive or negative.

    #     6. Think like a professional investor managing risk-adjusted returns.""",
    #     f"Live research snapshot:\n{_research_text(research)}\n\nAgent findings:\n{_findings_text(findings)}",
    # )
    
    # print("########################################################")
    # print("Data from drivers:")
    # print(data)
    # print("########################################################")
    

    
    system_prompt = """
    You are a senior investment analyst with more than 30 years of experience
    and think like a professional investor managing risk-adjusted returns.

    Your task is to build an evidence-based investment thesis using ONLY the
    supplied live research and agent findings.

    Do not use outside knowledge.
    Do not invent facts.
    Do not infer unsupported financial metrics.
    Every important positive or negative statement must reference supporting evidence.

    ============================================================
    REQUIRED OUTPUT
    ============================================================

    Return ONLY valid JSON with this structure:

    {
        "company": "",
        "industry": "",
        "bull_case": [
            {
                "factor": "",
                "explanation": "",
                "evidence": "",
                "additional_evidence": "",
                "importance": "High|Medium|Low"
            }
        ],
        "bear_case": [
            {
                "factor": "",
                "explanation": "",
                "evidence": "",
                "additional_evidence": "",
                "importance": "High|Medium|Low"
            }
        ],
        "base_case": "",
        "confidence": 0,
        "confidence_explanation": "",
        "assumptions": [],
        "challenge": "",
        "competitors": [],
        "drivers": [
            {
                "name": "",
                "description": "",
                "importance": 1,
                "direction": "Positive|Negative|Neutral",
                "monitoring_required": true,
                "source_type": ""
            }
        ]
    }

    ============================================================
    INVESTMENT REASONING RULES
    ============================================================

    1. Never make a conclusion from a single data point.

    2. Evaluate the company across multiple investment dimensions:

       - Revenue growth
       - Profitability
       - EBITDA / operating margins
       - Net income
       - EPS and EPS growth
       - Debt position
       - Cash position
       - Net debt
       - Working capital
       - Debt/equity
       - Debt/assets
       - Operating cash flow
       - Capital expenditures
       - Free cash flow
       - FCF margin
       - FCF growth
       - Market share
       - Competitive pressure
       - Industry cycle
       - Management quality
       - Capital allocation
       - Valuation
       - Regulatory environment
       - Recent news and catalysts
       - Market price and market sentiment

    3. Financial analysis is REQUIRED whenever financial data is provided.

       You MUST incorporate:

       Financial Performance:
       - Revenue
       - Revenue growth
       - Gross margin
       - Operating margin
       - EBITDA margin when available
       - Net income
       - EPS
       - EPS growth
       - TTM versus prior fiscal years

       Financial Health:
       - Cash
       - Debt
       - Net debt
       - Working capital
       - Debt/equity
       - Debt/assets

       Cash Flow:
       - Operating cash flow
       - CapEx
       - Free cash flow
       - FCF margin
       - FCF growth
       - FCF conversion when available

       Include at least one bull or bear point grounded in
       financial statement evidence.

       Include at least TWO drivers sourced from financial metrics
       and use:
       "source_type": "Financial statements"

    4. When historical financial periods are available, compare:
       - TTM
       - Most recent fiscal year
       - Prior fiscal year

       Identify whether the trend is:
       - Improving
       - Deteriorating
       - Stable
       - Mixed

    5. Never treat a single metric as proof of overall business quality.

       For example:
       Revenue growth alone does not prove the company is financially strong.
       Consider profitability, cash flow, debt and competitive conditions together.

    6. Clearly separate:

       Facts:
       What the supplied evidence directly shows.

       Interpretation:
       What those facts imply for the business.

       Investment conclusion:
       What those combined factors imply for the investment thesis.

    ============================================================
    BULL CASE
    ============================================================

    Construct the bull case only from supplied evidence.

    Each bull-case item MUST be an object with these fields:
    - factor: Short name of the positive factor (e.g., "Strong Revenue Growth", "Expanding Operating Margins")
    - explanation: Why this factor matters for the investment thesis (2-3 sentences)
    - evidence: Specific evidence from findings (cite headlines, financial metrics, market data with numbers)
    - additional_evidence: Corroborating evidence from a second independent source (optional but preferred)
    - importance: "High" | "Medium" | "Low" — based on materiality to thesis

    Rules:
    - Every claim must reference specific evidence from findings
    - Prefer factors supported by more than one independent finding
    - Include at least one factor grounded in financial statements when available
    - Combine related evidence into a single factor rather than listing separately
    - Factor name should be specific, not generic (e.g., "TTM Revenue Growth of 8.2%" not "Revenue Growth")

============================================================
    BEAR CASE
    ============================================================

    Construct the bear case only from supplied evidence.

    Each bear-case item MUST be an object with these fields:
    - factor: Short name of the risk factor (e.g., "High Leverage Risk", "Declining FCF Conversion")
    - explanation: Why this risk matters for the investment thesis (2-3 sentences)
    - evidence: Specific evidence from findings (cite headlines, financial metrics, market data with numbers)
    - additional_evidence: Corroborating evidence from a second independent source (optional but preferred)
    - importance: "High" | "Medium" | "Low" — based on materiality to thesis

    Rules:
    - Every claim must reference specific evidence from findings
    - Identify whether the risk affects growth, profitability, liquidity, valuation, competition, or execution
    - Include at least one factor grounded in financial statements when available
    - Combine related evidence into a single factor rather than listing separately
    - Factor name should be specific, not generic (e.g., "Debt/Equity of 2.3x" not "High Debt")
    COMPETITIVE ANALYSIS
    ============================================================

    Evaluate competitors using the supplied research.

    Consider:
    - Product/service overlap
    - Customer overlap
    - Geography
    - Pricing pressure
    - Technology advantage
    - Market share
    - Scale
    - Margin pressure
    - Ability to take market share

    Do not invent competitor facts.

    ============================================================
    CONFIDENCE SCORE
    ============================================================

    Confidence measures the QUALITY, COMPLETENESS, CONSISTENCY and
    RECENCY of the evidence.

    Confidence does NOT measure whether the thesis is bullish or bearish.

    Use this framework:

    90-100:
    Very strong evidence across financial performance, financial health,
    cash flow, market data, competition, industry conditions and catalysts.
    Multiple independent sources support the major conclusions.
    Data is recent and internally consistent.
    Very few material unanswered questions remain.

    80-89:
    Strong evidence across most major investment dimensions.
    Some uncertainty remains, but the core thesis is well supported.

    70-79:
    Good evidence, but one or more important areas are incomplete,
    weakly supported or conflicting.

    60-69:
    Moderate evidence. Several important gaps or uncertainties exist.

    40-59:
    Weak or incomplete evidence. Major investment questions remain unanswered.

    0-39:
    Insufficient evidence to form a reliable investment thesis.

    ------------------------------------------------------------
    INCREASE CONFIDENCE WHEN:
    ------------------------------------------------------------

    - Multiple independent findings support the same conclusion.
    - Financial statements provide measurable trends.
    - TTM and fiscal-year trends agree.
    - Revenue, profitability and cash-flow trends are internally consistent.
    - Balance-sheet risk is measurable.
    - Cash and debt positions are clearly known.
    - Market and competitive evidence support the same conclusion.
    - Important claims are supported by primary or high-quality sources.
    - Recent information confirms older evidence.
    - Multiple agents independently identify the same material factor.
    - There are few unresolved contradictions.
    - Key investment questions have direct evidence-based answers.

    ------------------------------------------------------------
    DECREASE CONFIDENCE WHEN:
    ------------------------------------------------------------

    - Important information is missing.
    - Financial statements are unavailable.
    - Findings materially conflict.
    - Evidence is stale.
    - A major conclusion depends on an assumption rather than evidence.
    - Valuation cannot be assessed from available evidence.
    - Competitive position is unclear.
    - Management quality cannot be evaluated.
    - Regulatory or industry risks are unknown.
    - Financial trends cannot be established.
    - Important claims rely on only one weak source.
    - Multiple agents disagree and the conflict cannot be resolved.

    ------------------------------------------------------------
    IMPORTANT CONFIDENCE RULES:
    ------------------------------------------------------------

    Do NOT increase confidence merely because there are many findings.

    Do NOT increase confidence merely because the thesis sounds persuasive.

    Do NOT decrease confidence merely because the company has risks.

    A company can have a high-confidence bearish thesis.

    A company can have a low-confidence bullish thesis.

    Confidence must reflect evidence quality, not investment direction.

    If financial analysis is unavailable:
    - Reduce confidence.
    - Mention the limitation in assumptions.
    - Do not assume positive or negative financial quality.

    If critical data is missing:
    explicitly identify it in "assumptions" or "challenge".

    ============================================================
    EVIDENCE REQUIREMENTS
    ============================================================

    For every major bull or bear conclusion, identify the evidence
    supporting it.

    Prefer evidence from:
    - Financial statements
    - Market data
    - Company filings
    - High-quality financial news
    - Reliable agent findings

    Distinguish facts from interpretation.

    Never fabricate:
    - Financial figures
    - Market share
    - Competitor metrics
    - Management information
    - Valuation metrics
    - News events
    - Dates
    - Sources

    ============================================================
    FINAL THESIS REQUIREMENTS
    ============================================================

    The final thesis must synthesize the entire evidence set.

    Do not simply summarize individual agent findings.

    Resolve conflicts where possible.

    If conflicts cannot be resolved, explicitly mention the uncertainty
    and reduce confidence accordingly.

    The base case should represent the most reasonable interpretation
    of the total evidence, not simply the midpoint between the bull
    and bear cases.

    Drivers should represent the most important variables that could
    materially change the thesis in the future.

    Every driver must identify:
    - What the driver is
    - Why it matters
    - Direction
    - Importance
    - Whether it requires monitoring
    - Evidence source type
    """

    user_prompt = (
        "LIVE RESEARCH SNAPSHOT:\n"
        f"{_research_text(research)}\n\n"
        "AGENT FINDINGS:\n"
        f"{_findings_text(findings)}"
    )

    data = _chat_json(
        system_prompt,
        user_prompt,
    )
    
    drivers = [
        Driver(
            str(d.get("name", "Driver")),
            str(d.get("description", "")),
            max(1, min(10, int(d.get("importance", 5)))),
            str(d.get("direction", "Neutral")),
            bool(d.get("monitoring_required", True)),
            str(d.get("source_type", "Live research")),
        )
        for d in data.get("drivers", [])
        if d.get("name")
    ]
    # competitors = [str(c).strip() for c in data.get("competitors", research.get("competitors", [])) if str(c).strip()]
    # competitors =  discover_competitors(research["name"], research["industry"])
    
    competitor_data = discover_competitors(
        company=research.get("name", ""),
        industry=research.get("industry", ""),
        ticker=research.get("ticker", ""),
    )

    competitors = [
        c["company"]
        for c in competitor_data
        if c.get("company")
    ]
    
    bull_case = []
    for item in data.get("bull_case", [])[:5]:
        if isinstance(item, dict) and item.get("factor"):
            bull_case.append(ThesisPoint(
                factor=str(item.get("factor", "")),
                explanation=str(item.get("explanation", "")),
                evidence=str(item.get("evidence", "")),
                additional_evidence=str(item.get("additional_evidence", "")),
                importance=str(item.get("importance", "Medium"))
            ))
        elif isinstance(item, str) and item.strip():
            bull_case.append(ThesisPoint(
                factor=item.strip(),
                explanation="",
                evidence="From live research findings.",
                importance="Medium"
            ))
    if not bull_case:
        bull_case.append(ThesisPoint(
            factor="Insufficient live evidence",
            explanation="No clearly positive live signal was classified in the current research scan.",
            evidence="Research scan returned no usable positive findings.",
            importance="Low"
        ))

    bear_case = []
    for item in data.get("bear_case", [])[:5]:
        if isinstance(item, dict) and item.get("factor"):
            bear_case.append(ThesisPoint(
                factor=str(item.get("factor", "")),
                explanation=str(item.get("explanation", "")),
                evidence=str(item.get("evidence", "")),
                additional_evidence=str(item.get("additional_evidence", "")),
                importance=str(item.get("importance", "Medium"))
            ))
        elif isinstance(item, str) and item.strip():
            bear_case.append(ThesisPoint(
                factor=item.strip(),
                explanation="",
                evidence="From live research findings.",
                importance="Medium"
            ))
    if not bear_case:
        bear_case.append(ThesisPoint(
            factor="Insufficient live evidence",
            explanation="No clearly negative live signal was classified in the current research scan.",
            evidence="Research scan returned no usable negative findings.",
            importance="Low"
        ))

    return Thesis(
        company=str(data.get("company") or research.get("name") or research.get("company")),
        industry=str(data.get("industry") or research.get("industry") or "Unclassified"),
        bull_case=bull_case,
        bear_case=bear_case,
        base_case=str(data.get("base_case", "Evidence-led base case pending further monitoring.")),
        confidence=max(0, min(100, int(data.get("confidence", 50)))),
        assumptions=[str(x) for x in data.get("assumptions", [])][:6] or ["Live sources are current and attributed."],
        challenge=str(data.get("challenge", "Primary sources may contradict headline-level signals.")),
        drivers=drivers or [
            Driver("Live evidence monitoring", "Monitor incoming agent findings for material thesis changes.", 8, "Neutral", True, "Agent pipeline")
        ],
        competitors=competitors,
    )


def generate_triggers_with_llm(thesis: Thesis, findings: List[Dict[str, Any]]) -> List[Trigger] | None:
    if not llm_is_configured():
        return None
    import hashlib

    driver_list = [{"name": d.name, "description": d.description, "direction": d.direction, "importance": d.importance} for d in thesis.drivers]
    financial_findings = [f for f in findings if f.get("agent") == "Financial Agent" and f.get("status") == "Live"]
    has_financials = len(financial_findings) > 0

    system_prompt = """
You are a senior investment monitoring specialist. Generate PRECISE, ACTIONABLE monitoring triggers that an analyst can actually use to detect thesis changes.

================================================================================
CRITICAL RULES — VIOLATIONS MAKE TRIGGERS USELESS
================================================================================

1. SPECIFICITY OVER GENERICITY
   ❌ BAD: "Monitor revenue growth"
   ✅ GOOD: "TTM revenue growth falls below 5% (currently 8.2%) for two consecutive quarters"
   ❌ BAD: "Watch for margin deterioration"
   ✅ GOOD: "Operating margin drops below 12% (currently 15.3%) or declines >200bps QoQ"

2. EVERY TRIGGER MUST HAVE A CLEAR, MEASURABLE THRESHOLD
   - Use actual numbers from the thesis/findings (current values, historical ranges)
   - Define the exact condition that flips the trigger
   - Specify timeframe: "for 2 consecutive quarters", "in a single earnings release", "sustained for 30 days"

3. TIE EACH TRIGGER TO A SPECIFIC DRIVER BY EXACT NAME
   - The `related_driver` MUST match a driver name from the input exactly
   - If no driver matches, create a "General" trigger but explain why

4. CATEGORY MUST REFLECT THESIS DIRECTION, NOT EVENT SENTIMENT
   - Positive driver → Negative category trigger (risk to bull case)
   - Negative driver → Positive category trigger (risk to bear case)
   - Neutral driver → Hold category

5. FINANCIAL TRIGGERS REQUIRE FINANCIAL DATA
   - Only create revenue/margin/leverage/FCF/EPS triggers if Financial Agent findings are Live
   - If financials are Unavailable, DO NOT invent financial thresholds

6. NEWS TRIGGERS: USE SPECIFIC CONDITION TYPES
   - keyword: Specific terms that must appear in headlines (e.g., "bankruptcy", "FDA approval", "merger")
   - sentiment: Sustained negative/positive sentiment over N periods (e.g., "≥3 negative headlines in 7 days")
   - volume: Headline count spike vs baseline (e.g., "headline count > 2x 7-day average")

7. AVOID THESE COMMON FAILURES:
   ❌ Triggers that fire on normal volatility (e.g., "stock moves >1%")
   ❌ Triggers without a source (e.g., "monitor news" — which source?)
   ❌ Triggers that are unactionable (e.g., "watch competitive landscape")
   ❌ Duplicate triggers for the same metric with different thresholds
   ❌ Triggers for metrics not in the thesis/findings
   ❌ Vague timeframes ("regularly", "periodically")

8. MONITORING FREQUENCY MUST MATCH DATA AVAILABILITY
   - Hours: only for real-time market data (price, volume)
   - Daily: news, RSS feeds, daily price
   - Weekly: earnings, filings, quarterly financials
   - Monthly: annual reports, major strategic updates

================================================================================
OUTPUT FORMAT — RETURN ONLY VALID JSON
================================================================================
{
  "triggers": [
    {
      "category": "Positive|Negative|Hold",
      "description": "Human-readable condition with threshold, timeframe, and data source",
      "confidence": 0-100,
      "importance": "Critical|High|Medium",
      "related_driver": "Exact driver name from input",
      "monitoring_frequency": "Hours|Daily|Weekly",
      "data_source": "yahoo_finance_financials|google_news_rss|yahoo_finance_rss|yahoo_finance_price",
      "threshold": "Exact numeric/qualitative condition",
      "current_value": "Current reading from findings (if available)",
      "condition": {
        "condition_type": "financial_metric|news_keyword|news_sentiment|news_volume|price_change",
        "metric_name": "revenue_growth_ttm|operating_margin_ttm|net_debt_ttm|fcf_ttm|eps_ttm|debt_to_equity_ttm|...",
        "operator": "<|>|<=|>=|==|!=",
        "threshold": 5.0,
        "unit": "percent|ratio|absolute|count",
        "lookback_periods": 2,
        "period_type": "quarterly|annual|daily",
        "consecutive": true,
        "allow_gaps": true,
        "keywords": ["bankruptcy", "FDA approval", "merger"],
        "sentiment_threshold": -0.3,
        "volume_multiplier": 2.0
      }
    }
  ]
}

================================================================================
CONDITION TYPE SPECIFICATIONS
================================================================================

1. financial_metric (data_source: "yahoo_finance_financials")
   - metric_name: One of: revenue_growth_ttm, operating_margin_ttm, gross_margin_ttm, 
     net_debt_ttm, fcf_ttm, eps_ttm, debt_to_equity_ttm, debt_to_assets_ttm,
     revenue_ttm, operating_income_ttm, net_income_ttm, cash_ttm, working_capital_ttm
   - operator: <, >, <=, >=
   - threshold: numeric value
   - unit: "percent" for margins/growth, "ratio" for leverage, "absolute" for dollar amounts
   - lookback_periods: number of periods to check
   - period_type: "quarterly" (default) or "annual"
   - consecutive: true = must meet threshold for N consecutive periods
   - allow_gaps: true = use last N available periods if some missing

2. news_keyword (data_source: "google_news_rss" or "yahoo_finance_rss")
   - keywords: array of terms that trigger when found in headlines
   - lookback_periods: time window in days (e.g., 7 for last week)
   - threshold: count of matching headlines required (default 1)
   - unit: "count"

3. news_sentiment (data_source: "google_news_rss" or "yahoo_finance_rss")
   - sentiment_threshold: -1 to 1 (negative threshold like -0.3 means sustained negative)
   - lookback_periods: time window in days
   - threshold: minimum count of headlines with sentiment beyond threshold
   - unit: "count"

4. news_volume (data_source: "google_news_rss" or "yahoo_finance_rss")
   - volume_multiplier: spike factor vs baseline (e.g., 2.0 = 2x average)
   - lookback_periods: baseline window in days
   - threshold: minimum absolute count
   - unit: "count"

5. price_change (data_source: "yahoo_finance_price")
   - metric_name: "price_change_pct" or "volume_change_pct"
   - operator: <, >, <=, >=
   - threshold: percentage value
   - unit: "percent"
   - lookback_periods: 1 (intraday) or more for sustained moves

================================================================================
EXAMPLES OF HIGH-QUALITY TRIGGERS WITH STRUCTURED CONDITIONS
================================================================================

Driver: "Revenue growth trend" (Positive, importance 8, source: Financial statements)
Current: TTM revenue growth +8.2%
Trigger: {
  "category": "Negative",
  "description": "TTM revenue growth decelerates below 5% for two consecutive quarterly reports, signaling growth thesis breakdown",
  "confidence": 85,
  "importance": "Critical",
  "related_driver": "Revenue growth trend",
  "monitoring_frequency": "Weekly",
  "data_source": "yahoo_finance_financials",
  "threshold": "TTM revenue growth < 5% for 2 consecutive quarters",
  "current_value": "+8.2%",
  "condition": {
    "condition_type": "financial_metric",
    "metric_name": "revenue_growth_ttm",
    "operator": "<",
    "threshold": 5.0,
    "unit": "percent",
    "lookback_periods": 2,
    "period_type": "quarterly",
    "consecutive": true,
    "allow_gaps": true,
    "data_source": "yahoo_finance_financials"
  }
}

Driver: "Operating profitability" (Positive, importance 7, source: Financial statements)
Current: TTM operating margin 15.3%
Trigger: {
  "category": "Negative",
  "description": "Operating margin contracts below 12% (200bps below current) in any single quarter, indicating pricing power erosion",
  "confidence": 80,
  "importance": "High",
  "related_driver": "Operating profitability",
  "monitoring_frequency": "Weekly",
  "data_source": "yahoo_finance_financials",
  "threshold": "Quarterly operating margin < 12%",
  "current_value": "15.3%",
  "condition": {
    "condition_type": "financial_metric",
    "metric_name": "operating_margin_ttm",
    "operator": "<",
    "threshold": 12.0,
    "unit": "percent",
    "lookback_periods": 1,
    "period_type": "quarterly",
    "consecutive": false,
    "allow_gaps": true,
    "data_source": "yahoo_finance_financials"
  }
}

Driver: "Regulatory risk" (Negative, importance 9, source: Live news)
Trigger: {
  "category": "Positive",
  "description": "Regulatory headlines containing 'investigation', 'probe', 'enforcement', or 'fine' appear in Google News RSS for the company",
  "confidence": 75,
  "importance": "High",
  "related_driver": "Regulatory risk",
  "monitoring_frequency": "Daily",
  "data_source": "google_news_rss",
  "threshold": "Any headline containing regulatory enforcement keywords",
  "current_value": "No regulatory headlines in last 7 days",
  "condition": {
    "condition_type": "news_keyword",
    "keywords": ["investigation", "probe", "enforcement", "fine", "sanction", "violation"],
    "lookback_periods": 7,
    "threshold": 1,
    "unit": "count",
    "data_source": "google_news_rss"
  }
}

Driver: "Negative sentiment spike" (Negative, importance 8, source: Live news)
Trigger: {
  "category": "Positive",
  "description": "Sustained negative news sentiment: 3 or more negative headlines in any 7-day period from Google News RSS",
  "confidence": 70,
  "importance": "Medium",
  "related_driver": "Negative sentiment spike",
  "monitoring_frequency": "Daily",
  "data_source": "google_news_rss",
  "threshold": "≥3 negative headlines (sentiment < -0.3) in 7 days",
  "current_value": "1 negative headline in last 7 days",
  "condition": {
    "condition_type": "news_sentiment",
    "sentiment_threshold": -0.3,
    "lookback_periods": 7,
    "threshold": 3,
    "unit": "count",
    "data_source": "google_news_rss"
  }
}

Driver: "News volume spike" (Neutral, importance 6, source: Live news)
Trigger: {
  "category": "Hold",
  "description": "Unusual news volume: headline count exceeds 2x the 30-day average, indicating potential catalyst",
  "confidence": 65,
  "importance": "Medium",
  "related_driver": "News volume spike",
  "monitoring_frequency": "Daily",
  "data_source": "google_news_rss",
  "threshold": "Headline count > 2x 30-day average (min 5 headlines)",
  "current_value": "Average 3 headlines/day over 30 days",
  "condition": {
    "condition_type": "news_volume",
    "volume_multiplier": 2.0,
    "lookback_periods": 30,
    "threshold": 5,
    "unit": "count",
    "data_source": "google_news_rss"
  }
}

================================================================================
VALIDATION CHECKLIST — EVERY TRIGGER MUST PASS
================================================================================
□ Description contains a specific threshold (number, %, or explicit condition)
□ Description specifies timeframe (consecutive quarters, single report, sustained period)
□ data_source matches an actual available source from findings
□ related_driver matches input driver name exactly
□ category opposes driver direction for risk triggers
□ monitoring_frequency matches data_source update cadence
□ current_value reflects actual finding data (not invented)
□ condition object has all required fields for its condition_type
□ Trigger is actionable — analyst knows exactly what to verify
"""

    user_prompt = f"""THESIS CONTEXT:
Company: {thesis.company} ({thesis.industry})
Thesis Confidence: {thesis.confidence}/100

DRIVERS (name, direction, importance, description):
{json.dumps(driver_list, indent=2)}

LIVE FINDINGS:
{_findings_text(findings)}

FINANCIAL DATA AVAILABLE: {has_financials}
{"Current financial metrics from Financial Agent findings:" if has_financials else "NO financial statement data available — DO NOT create financial metric triggers."}
{json.dumps([{"agent": f.get("agent"), "finding": f.get("finding"), "impact": f.get("impact")} for f in financial_findings], indent=2) if has_financials else ""}

Generate 5-8 triggers following ALL rules above. Prioritize Critical/High importance triggers tied to highest-importance drivers.
Each trigger MUST include a complete "condition" object matching its condition_type.
"""

    data = _chat_json(system_prompt, user_prompt)
    # print("########################################################")
    # print("Data from generate_triggers_with_llm:")
    # print(data)
    # print("########################################################")
    output: List[Trigger] = []
    for item in data.get("triggers", [])[:10]:
        description = str(item.get("description", "")).strip()
        if not description:
            continue
        category = str(item.get("category", "Hold"))
        raw = f"{thesis.company}:{category}:{description}".encode()
        condition = item.get("condition")
        # Include main company in related_companies for tracking
        related_companies = ", ".join([thesis.company] + thesis.competitors)
        output.append(
            Trigger(
                "TRG-" + hashlib.sha1(raw).hexdigest()[:7].upper(),
                category,
                description,
                max(0, min(100, int(item.get("confidence", thesis.confidence)))),
                str(item.get("importance", "Medium")),
                str(item.get("related_driver", thesis.drivers[0].name if thesis.drivers else "General")),
                related_companies,
                thesis.industry,
                str(item.get("monitoring_frequency", "Daily")),
                condition=condition,
            )
        )
        # print("########################################################")
        # print("Trigger from generate_triggers_with_llm:")
        # print(output)
        # print("########################################################")
    return output or None


def evaluate_with_llm(event: str, thesis: Thesis, triggers: List[Trigger]) -> Tuple[Dict[str, Any], List[Trigger]] | None:
    if not llm_is_configured():
        return None
    trigger_list = [{"id": t.trigger_id, "category": t.category, "description": t.description, "related_driver": t.related_driver, "status": t.status} for t in triggers]
    data = _chat_json(
        "You are an investment analyst evaluating a new event against an existing thesis and trigger set. "
        "Return JSON with keys: outcome, impact (Positive|Negative|Unclear), confidence (0-100), "
        "recommendation, evidence, matched_trigger_ids (array of trigger id strings from the input list). "
        "Only match triggers when the event materially relates to them.",
        f"Event:\n{event}\n\n"
        f"Thesis summary: {thesis.company}, {thesis.industry}, confidence {thesis.confidence}\n"
        f"Base case: {thesis.base_case}\n"
        f"Assumptions: {thesis.assumptions}\n"
        f"Triggers: {json.dumps(trigger_list)}",
    )
    matched_ids = {str(x) for x in data.get("matched_trigger_ids", [])}
    matched = [t for t in triggers if t.trigger_id in matched_ids]
    evaluation = {
        "event": event,
        "outcome": str(data.get("outcome", "Needs analyst review")),
        "impact": str(data.get("impact", "Unclear")),
        "confidence": max(0, min(100, int(data.get("confidence", 50)))),
        "recommendation": str(data.get("recommendation", "Review primary sources before acting.")),
        "evidence": str(data.get("evidence", "LLM assessment based on event text and thesis context.")),
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "matched_trigger_ids": [t.trigger_id for t in matched],
    }
    return evaluation, matched


def assess_findings_with_llm(findings: List[Dict[str, Any]], thesis: Thesis, triggers: List[Trigger]) -> Dict[str, Any] | None:
    if not llm_is_configured():
        return None
    live = [f for f in findings if f.get("status") == "Live"]
    trigger_list = [{"id": t.trigger_id, "description": t.description, "related_driver": t.related_driver} for t in triggers]
    data = _chat_json(
        "You are an investment analyst synthesizing live agent findings against a thesis. "
        "Return JSON with keys: stance (Improving|Deteriorating|Stable / mixed), outcome, "
        "impact (Positive|Negative|Unclear), confidence (0-100), recommendation, evidence, "
        "matched_trigger_ids (array of trigger ids that should change status). "
        "Use only the supplied findings; note gaps when sources are unavailable.",
        f"Thesis: {thesis.company}, confidence {thesis.confidence}, industry {thesis.industry}\n"
        f"Base case: {thesis.base_case}\n"
        f"Triggers: {json.dumps(trigger_list)}\n"
        f"Live findings:\n{_findings_text(live)}",
    )
    positives = sum(f.get("impact") == "Positive" for f in live)
    negatives = sum(f.get("impact") == "Negative" for f in live)
    matched_ids = [str(x) for x in data.get("matched_trigger_ids", [])]
    return {
        "agent": "Investment Analyst Agent",
        "stance": str(data.get("stance", "Stable / mixed")),
        "outcome": str(data.get("outcome", "Live scan completed")),
        "impact": str(data.get("impact", "Unclear")),
        "confidence": max(0, min(100, int(data.get("confidence", 50)))),
        "recommendation": str(data.get("recommendation", "Continue monitoring.")),
        "evidence": str(data.get("evidence", "Synthesized from live agent findings.")),
        "live_sources": len(live),
        "positive_signals": positives,
        "negative_signals": negatives,
        "matched_trigger_ids": matched_ids,
    }
