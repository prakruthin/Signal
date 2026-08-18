"""Financial Agent — income statement, balance sheet, and cash flow analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


PERIOD_LABELS = ("TTM", "FY-1", "FY-2", "FY-3", "FY-4")
SOURCE = "Yahoo Finance via yfinance"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class FinancialSnapshot:
    company: str
    ticker: str
    currency: str
    fiscal_periods: List[str] = field(default_factory=list)
    performance: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)
    health: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)
    cash_flow: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)
    status: str = "Unavailable"
    source: str = SOURCE
    observed_at: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "ticker": self.ticker,
            "currency": self.currency,
            "fiscal_periods": self.fiscal_periods,
            "performance": self.performance,
            "health": self.health,
            "cash_flow": self.cash_flow,
            "status": self.status,
            "source": self.source,
            "observed_at": self.observed_at,
            "notes": self.notes,
        }


def _safe_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator * 100, 2)


def _growth(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior in (None, 0):
        return None
    return round((current - prior) / abs(prior) * 100, 2)


def _format_large(value: Optional[float], currency: str = "") -> str:
    if value is None:
        return "N/A"
    sign = "-" if value < 0 else ""
    amount = abs(value)
    suffix = currency.strip()
    if amount >= 1_000_000_000_000:
        return f"{sign}{amount / 1_000_000_000_000:.2f}T{(' ' + suffix) if suffix else ''}"
    if amount >= 1_000_000_000:
        return f"{sign}{amount / 1_000_000_000:.2f}B{(' ' + suffix) if suffix else ''}"
    if amount >= 1_000_000:
        return f"{sign}{amount / 1_000_000:.2f}M{(' ' + suffix) if suffix else ''}"
    return f"{sign}{amount:,.0f}{(' ' + suffix) if suffix else ''}"


def _format_pct(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value:+.2f}%" if value < 0 else f"{value:.2f}%"


def _format_ratio(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value:.2f}x"


def _period_label(date_value: Any) -> str:
    if hasattr(date_value, "strftime"):
        return date_value.strftime("%Y-%m-%d")
    return str(date_value)


def _find_row(df: pd.DataFrame, *names: str) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None
    for name in names:
        if name in df.index:
            return df.loc[name]
    lowered = {str(idx).lower(): idx for idx in df.index}
    for name in names:
        key = name.lower()
        for label, idx in lowered.items():
            if key in label:
                return df.loc[idx]
    return None


def _annual_periods(df: pd.DataFrame, limit: int = 4) -> List[Any]:
    if df is None or df.empty:
        return []
    return list(df.columns[:limit])


def _quarterly_ttm(df: pd.DataFrame, row_names: Tuple[str, ...]) -> Optional[float]:
    row = _find_row(df, *row_names)
    if row is None:
        return None
    values = [_safe_float(v) for v in row.iloc[:4]]
    if any(v is None for v in values):
        return None
    total = sum(v for v in values if v is not None)
    if "Capital Expenditure" in row_names or any("capex" in n.lower() for n in row_names):
        return total
    return total


def _series_for_periods(df: pd.DataFrame, row_names: Tuple[str, ...], periods: List[Any]) -> Dict[str, Optional[float]]:
    row = _find_row(df, *row_names)
    output: Dict[str, Optional[float]] = {}
    if row is None:
        return {label: None for label in PERIOD_LABELS}
    annual_values = [_safe_float(row.get(period)) for period in periods]
    for idx, label in enumerate(PERIOD_LABELS[1:]):
        output[label] = annual_values[idx] if idx < len(annual_values) else None
    return output


def _latest_point_in_time(df: pd.DataFrame, row_names: Tuple[str, ...], periods: List[Any]) -> Dict[str, Optional[float]]:
    row = _find_row(df, *row_names)
    output: Dict[str, Optional[float]] = {label: None for label in PERIOD_LABELS}
    if row is None:
        return output
    annual_values = [_safe_float(row.get(period)) for period in periods]
    for idx, label in enumerate(PERIOD_LABELS):
        if idx == 0:
            output[label] = annual_values[0] if annual_values else None
        elif idx - 1 < len(annual_values):
            output[label] = annual_values[idx - 1]
    return output


def _margin_series(numerator: Dict[str, Optional[float]], denominator: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    return {label: _pct(numerator.get(label), denominator.get(label)) for label in PERIOD_LABELS}


def _growth_series(values: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    ordered = [values.get(label) for label in PERIOD_LABELS]
    growth: Dict[str, Optional[float]] = {label: None for label in PERIOD_LABELS}
    for idx in range(len(PERIOD_LABELS) - 1):
        growth[PERIOD_LABELS[idx]] = _growth(ordered[idx], ordered[idx + 1])
    return growth


def _fcf_conversion(fcf: Dict[str, Optional[float]], net_income: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    return {label: _pct(fcf.get(label), net_income.get(label)) for label in PERIOD_LABELS}


def _financial_impact(snapshot: FinancialSnapshot) -> str:
    perf = snapshot.performance
    health = snapshot.health
    cf = snapshot.cash_flow
    score = 0
    revenue_growth = perf.get("revenue_growth", {}).get("TTM")
    if revenue_growth is not None:
        score += 1 if revenue_growth > 5 else -1 if revenue_growth < -5 else 0
    op_margin = perf.get("operating_margin", {}).get("TTM")
    if op_margin is not None:
        score += 1 if op_margin > 15 else -1 if op_margin < 5 else 0
    net_income = perf.get("net_income", {}).get("TTM")
    if net_income is not None:
        score += 1 if net_income > 0 else -1
    debt_equity = health.get("debt_to_equity", {}).get("TTM")
    if debt_equity is not None:
        score += -1 if debt_equity > 2 else 1 if debt_equity < 0.5 else 0
    fcf = cf.get("free_cash_flow", {}).get("TTM")
    if fcf is not None:
        score += 1 if fcf > 0 else -1
    if score >= 2:
        return "Positive"
    if score <= -2:
        return "Negative"
    return "Neutral"


def _period_header(periods: List[str], period_keys: List[str], key: str) -> str:
    if key in period_keys:
        idx = period_keys.index(key)
        if idx < len(periods):
            return periods[idx]
    return key


def _metric_line(
    label: str,
    values: Dict[str, Optional[float]],
    periods: List[str],
    period_keys: List[str],
    currency: str,
    kind: str = "money",
) -> str:
    parts = []
    for key in period_keys:
        value = (values or {}).get(key)
        header = _period_header(periods, period_keys, key)
        if value is None:
            parts.append(f"{header}: N/A")
        elif kind == "pct":
            parts.append(f"{header}: {value:.2f}%")
        elif kind == "ratio":
            parts.append(f"{header}: {value:.2f}x")
        elif kind == "eps":
            parts.append(f"{header}: {value:.2f}")
        else:
            parts.append(f"{header}: {_format_large(value, currency)}")
    return f"  {label}: " + "; ".join(parts)


def financial_thesis_context(financials: Dict[str, Any]) -> str:
    """Structured financial statement text for LLM thesis generation."""
    if not financials or financials.get("status") != "Live":
        return (
            "Financial analysis: unavailable. "
            "Thesis must note missing financial statement coverage and reduce confidence accordingly."
        )

    periods = financials.get("fiscal_periods") or list(PERIOD_LABELS)
    period_keys = list(PERIOD_LABELS)
    currency = financials.get("currency") or ""
    perf = financials.get("performance") or {}
    health = financials.get("health") or {}
    cf = financials.get("cash_flow") or {}
    impact = _financial_impact(
        FinancialSnapshot(
            company=str(financials.get("company") or ""),
            ticker=str(financials.get("ticker") or ""),
            currency=currency,
            performance=perf,
            health=health,
            cash_flow=cf,
            status="Live",
        )
    )

    def line(label: str, values: Dict[str, Optional[float]], kind: str = "money") -> str:
        return _metric_line(label, values, periods, period_keys, currency, kind)

    return "\n".join(
        [
            f"Financial analysis for {financials.get('company')} ({financials.get('ticker')}) — overall signal: {impact}",
            "Use these figures in bull/bear cases, base case, drivers, and confidence. Cite specific numbers and periods.",
            "",
            "Financial Performance (income statement):",
            line("Revenue", perf.get("revenue", {})),
            line("Revenue growth", perf.get("revenue_growth", {}), "pct"),
            line("Gross profit", perf.get("gross_profit", {})),
            line("Gross margin", perf.get("gross_margin", {}), "pct"),
            line("Operating income", perf.get("operating_income", {})),
            line("Operating margin", perf.get("operating_margin", {}), "pct"),
            line("EBITDA", perf.get("ebitda", {})),
            line("EBITDA margin", perf.get("ebitda_margin", {}), "pct"),
            line("Net income", perf.get("net_income", {})),
            line("EPS", perf.get("eps", {}), "eps"),
            line("EPS growth", perf.get("eps_growth", {}), "pct"),
            "",
            "Financial Health (balance sheet):",
            line("Cash", health.get("cash", {})),
            line("Debt", health.get("debt", {})),
            line("Net debt", health.get("net_debt", {})),
            line("Current assets", health.get("current_assets", {})),
            line("Current liabilities", health.get("current_liabilities", {})),
            line("Working capital", health.get("working_capital", {})),
            line("Equity", health.get("equity", {})),
            line("Debt / equity", health.get("debt_to_equity", {}), "ratio"),
            line("Debt / assets", health.get("debt_to_assets", {}), "ratio"),
            "",
            "Cash Flow Analysis:",
            line("Operating cash flow", cf.get("operating_cash_flow", {})),
            line("CapEx", cf.get("capex", {})),
            line("Free cash flow", cf.get("free_cash_flow", {})),
            line("FCF margin", cf.get("fcf_margin", {}), "pct"),
            line("FCF growth", cf.get("fcf_growth", {}), "pct"),
            line("FCF conversion", cf.get("fcf_conversion", {}), "pct"),
        ]
    )


def financial_thesis_signals(financials: Dict[str, Any]) -> Dict[str, Any]:
    """Derive bull/bear points and drivers from financial statements for non-LLM thesis fallback."""
    empty: Dict[str, Any] = {"bull": [], "bear": [], "drivers": [], "impact": "Unclear", "available": False}
    if not financials or financials.get("status") != "Live":
        return empty

    perf = financials.get("performance") or {}
    health = financials.get("health") or {}
    cf = financials.get("cash_flow") or {}
    currency = financials.get("currency") or ""
    impact = _financial_impact(
        FinancialSnapshot(
            company=str(financials.get("company") or ""),
            ticker=str(financials.get("ticker") or ""),
            currency=currency,
            performance=perf,
            health=health,
            cash_flow=cf,
            status="Live",
        )
    )
    bull: List[str] = []
    bear: List[str] = []
    drivers: List[Dict[str, Any]] = []

    revenue_growth = perf.get("revenue_growth", {}).get("TTM")
    if revenue_growth is not None:
        point = f"TTM revenue growth is {revenue_growth:+.2f}%."
        (bull if revenue_growth > 3 else bear if revenue_growth < 0 else bull).append(point)
        drivers.append(
            {
                "name": "Revenue growth trend",
                "description": point,
                "importance": 8,
                "direction": "Positive" if revenue_growth > 3 else "Negative" if revenue_growth < 0 else "Neutral",
                "source_type": "Financial statements",
            }
        )

    op_margin = perf.get("operating_margin", {}).get("TTM")
    if op_margin is not None:
        point = f"TTM operating margin is {op_margin:.2f}%."
        (bull if op_margin > 15 else bear if op_margin < 8 else bull).append(point)
        drivers.append(
            {
                "name": "Operating profitability",
                "description": point,
                "importance": 7,
                "direction": "Positive" if op_margin > 15 else "Negative" if op_margin < 8 else "Neutral",
                "source_type": "Financial statements",
            }
        )

    eps_growth = perf.get("eps_growth", {}).get("TTM")
    if eps_growth is not None:
        point = f"TTM EPS growth is {eps_growth:+.2f}%."
        (bull if eps_growth > 5 else bear if eps_growth < 0 else bull).append(point)

    net_debt = health.get("net_debt", {}).get("TTM")
    cash = health.get("cash", {}).get("TTM")
    if net_debt is not None:
        point = f"Net debt (TTM) is {_format_large(net_debt, currency)}; cash is {_format_large(cash, currency)}."
        (bear if net_debt > 0 else bull).append(point)
        drivers.append(
            {
                "name": "Balance sheet leverage",
                "description": point,
                "importance": 8,
                "direction": "Negative" if net_debt > 0 else "Positive",
                "source_type": "Financial statements",
            }
        )

    debt_equity = health.get("debt_to_equity", {}).get("TTM")
    if debt_equity is not None:
        point = f"Debt/equity ratio (TTM) is {debt_equity:.2f}x."
        (bear if debt_equity > 1.5 else bull).append(point)

    fcf = cf.get("free_cash_flow", {}).get("TTM")
    fcf_margin = cf.get("fcf_margin", {}).get("TTM")
    if fcf is not None:
        margin_text = f"; FCF margin {fcf_margin:.2f}%" if fcf_margin is not None else ""
        point = f"TTM free cash flow is {_format_large(fcf, currency)}{margin_text}."
        (bull if fcf > 0 else bear).append(point)
        drivers.append(
            {
                "name": "Free cash flow generation",
                "description": point,
                "importance": 9,
                "direction": "Positive" if fcf > 0 else "Negative",
                "source_type": "Financial statements",
            }
        )

    fcf_conversion = cf.get("fcf_conversion", {}).get("TTM")
    if fcf_conversion is not None:
        point = f"FCF conversion (FCF / net income, TTM) is {fcf_conversion:.2f}%."
        (bull if fcf_conversion > 80 else bear if fcf_conversion < 50 else bull).append(point)

    return {"bull": bull, "bear": bear, "drivers": drivers, "impact": impact, "available": True}


def financial_markdown(snapshot: Dict[str, Any]) -> str:
    if snapshot.get("status") != "Live":
        notes = snapshot.get("notes") or ["Financial data could not be retrieved."]
        return "## Financial analysis\n\n" + "\n".join(f"- {note}" for note in notes)

    periods = snapshot.get("fiscal_periods") or list(PERIOD_LABELS)
    period_keys = list(PERIOD_LABELS)
    currency = snapshot.get("currency") or ""
    perf = snapshot.get("performance") or {}
    health = snapshot.get("health") or {}
    cf = snapshot.get("cash_flow") or {}

    def row(label: str, values: Dict[str, Optional[float]], kind: str = "money") -> str:
        cells = []
        for period_key in period_keys:
            value = values.get(period_key)
            if kind == "pct":
                cells.append(_format_pct(value))
            elif kind == "ratio":
                cells.append(_format_ratio(value))
            elif kind == "eps":
                cells.append("N/A" if value is None else f"{value:.2f}")
            else:
                cells.append(_format_large(value, currency))
        return "| " + label + " | " + " | ".join(cells) + " |"

    def section(title: str, rows: List[str]) -> str:
        header = "| Metric | " + " | ".join(periods) + " |"
        divider = "| --- | " + " | ".join("---" for _ in periods) + " |"
        return f"### {title}\n\n" + "\n".join([header, divider, *rows])

    performance_rows = [
        row("Revenue", perf.get("revenue", {})),
        row("Revenue growth", perf.get("revenue_growth", {}), "pct"),
        row("Gross profit", perf.get("gross_profit", {})),
        row("Gross margin", perf.get("gross_margin", {}), "pct"),
        row("Operating income", perf.get("operating_income", {})),
        row("Operating margin", perf.get("operating_margin", {}), "pct"),
        row("EBITDA", perf.get("ebitda", {})),
        row("EBITDA margin", perf.get("ebitda_margin", {}), "pct"),
        row("Net income", perf.get("net_income", {})),
        row("EPS", perf.get("eps", {}), "eps"),
        row("EPS growth", perf.get("eps_growth", {}), "pct"),
    ]
    health_rows = [
        row("Cash", health.get("cash", {})),
        row("Debt", health.get("debt", {})),
        row("Net debt", health.get("net_debt", {})),
        row("Current assets", health.get("current_assets", {})),
        row("Current liabilities", health.get("current_liabilities", {})),
        row("Working capital", health.get("working_capital", {})),
        row("Equity", health.get("equity", {})),
        row("Debt / equity", health.get("debt_to_equity", {}), "ratio"),
        row("Debt / assets", health.get("debt_to_assets", {}), "ratio"),
    ]
    cashflow_rows = [
        row("Operating cash flow", cf.get("operating_cash_flow", {})),
        row("CapEx", cf.get("capex", {})),
        row("Free cash flow", cf.get("free_cash_flow", {})),
        row("FCF margin", cf.get("fcf_margin", {}), "pct"),
        row("FCF growth", cf.get("fcf_growth", {}), "pct"),
        row("FCF conversion", cf.get("fcf_conversion", {}), "pct"),
    ]

    notes = snapshot.get("notes") or []
    notes_block = "\n".join(f"- {note}" for note in notes)
    return (
        f"## Financial analysis — {snapshot.get('company')} ({snapshot.get('ticker')})\n\n"
        f"**Source:** {snapshot.get('source')}  \n"
        f"**Observed:** {snapshot.get('observed_at')}  \n"
        f"**Currency:** {currency or 'reported'}\n\n"
        + section("Financial Performance", performance_rows)
        + "\n\n"
        + section("Financial Health", health_rows)
        + "\n\n"
        + section("Cash Flow Analysis", cashflow_rows)
        + (f"\n\n**Notes**\n{notes_block}" if notes_block else "")
    )


class FinancialAgent:
    name = "Financial Agent"

    def collect(self, ticker: str, company: str = "") -> Tuple[FinancialSnapshot, List[Any]]:
        from .agents import AgentFinding
        observed = _now()
        label = company.strip() or ticker.strip().upper()
        if not ticker or ticker == "—":
            snapshot = FinancialSnapshot(
                company=label,
                ticker=ticker,
                currency="",
                status="Skipped",
                observed_at=observed,
                notes=["No ticker is configured for this company."],
            )
            finding = AgentFinding(
                self.name,
                "Skipped",
                observed,
                "Financial analysis skipped because no ticker was resolved.",
                SOURCE,
                impact="Unclear",
            )
            return snapshot, [finding]

        try:
            import yfinance as yf
        except ImportError:
            snapshot = FinancialSnapshot(
                company=label,
                ticker=ticker.upper(),
                currency="",
                status="Unavailable",
                observed_at=observed,
                notes=["Install yfinance to enable financial statement retrieval."],
            )
            finding = AgentFinding(
                self.name,
                "Unavailable",
                observed,
                "Financial data unavailable (yfinance is not installed).",
                SOURCE,
                impact="Unclear",
            )
            return snapshot, [finding]

        try:
            stock = yf.Ticker(ticker.upper())
            info = stock.info or {}
            income = stock.financials
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            q_income = stock.quarterly_financials
            q_balance = stock.quarterly_balance_sheet
            q_cashflow = stock.quarterly_cashflow

            annual_periods = _annual_periods(income, 4)
            fiscal_periods = list(PERIOD_LABELS)
            if annual_periods:
                fiscal_periods = ["TTM"] + [_period_label(p) for p in annual_periods[:4]]

            currency = info.get("currency") or info.get("financialCurrency") or ""

            revenue = _series_for_periods(income, ("Total Revenue", "Operating Revenue"), annual_periods)
            revenue["TTM"] = _quarterly_ttm(q_income, ("Total Revenue", "Operating Revenue")) or _safe_float(info.get("totalRevenue"))

            gross_profit = _series_for_periods(income, ("Gross Profit",), annual_periods)
            gross_profit["TTM"] = _quarterly_ttm(q_income, ("Gross Profit",))

            operating_income = _series_for_periods(income, ("Operating Income", "EBIT"), annual_periods)
            operating_income["TTM"] = _quarterly_ttm(q_income, ("Operating Income", "EBIT"))

            ebitda = _series_for_periods(income, ("EBITDA", "Normalized EBITDA"), annual_periods)
            ebitda["TTM"] = _quarterly_ttm(q_income, ("EBITDA", "Normalized EBITDA")) or _safe_float(info.get("ebitda"))

            net_income = _series_for_periods(income, ("Net Income", "Net Income Common Stockholders"), annual_periods)
            net_income["TTM"] = _quarterly_ttm(q_income, ("Net Income", "Net Income Common Stockholders")) or _safe_float(info.get("netIncomeToCommon"))

            eps = _series_for_periods(income, ("Diluted EPS", "Basic EPS"), annual_periods)
            eps["TTM"] = _safe_float(info.get("trailingEps"))

            gross_margin = _margin_series(gross_profit, revenue)
            operating_margin = _margin_series(operating_income, revenue)
            ebitda_margin = _margin_series(ebitda, revenue)
            revenue_growth = _growth_series(revenue)
            eps_growth = _growth_series(eps)

            balance_periods = _annual_periods(balance, 4)
            cash = _latest_point_in_time(balance, ("Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"), balance_periods)
            debt = _latest_point_in_time(balance, ("Total Debt",), balance_periods)
            current_assets = _latest_point_in_time(balance, ("Current Assets", "Total Current Assets"), balance_periods)
            current_liabilities = _latest_point_in_time(balance, ("Current Liabilities", "Total Current Liabilities"), balance_periods)
            equity = _latest_point_in_time(balance, ("Stockholders Equity", "Total Equity Gross Minority Interest"), balance_periods)
            total_assets = _latest_point_in_time(balance, ("Total Assets",), balance_periods)

            if q_balance is not None and not q_balance.empty:
                latest_q = q_balance.columns[0]
                for target, names in (
                    (cash, ("Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")),
                    (debt, ("Total Debt",)),
                    (current_assets, ("Current Assets", "Total Current Assets")),
                    (current_liabilities, ("Current Liabilities", "Total Current Liabilities")),
                    (equity, ("Stockholders Equity", "Total Equity Gross Minority Interest")),
                    (total_assets, ("Total Assets",)),
                ):
                    row = _find_row(q_balance, *names)
                    if row is not None:
                        target["TTM"] = _safe_float(row.get(latest_q))

            cash["TTM"] = cash.get("TTM") or _safe_float(info.get("totalCash"))
            debt["TTM"] = debt.get("TTM") or _safe_float(info.get("totalDebt"))

            net_debt = {label: None for label in PERIOD_LABELS}
            working_capital = {label: None for label in PERIOD_LABELS}
            debt_to_equity = {label: None for label in PERIOD_LABELS}
            debt_to_assets = {label: None for label in PERIOD_LABELS}
            for period_label in PERIOD_LABELS:
                c = cash.get(period_label)
                d = debt.get(period_label)
                ca = current_assets.get(period_label)
                cl = current_liabilities.get(period_label)
                eq = equity.get(period_label)
                ta = total_assets.get(period_label)
                if c is not None and d is not None:
                    net_debt[period_label] = d - c
                if ca is not None and cl is not None:
                    working_capital[period_label] = ca - cl
                if d is not None and eq not in (None, 0):
                    debt_to_equity[period_label] = round(d / eq, 2)
                if d is not None and ta not in (None, 0):
                    debt_to_assets[period_label] = round(d / ta, 2)

            cf_periods = _annual_periods(cashflow, 4)
            operating_cash_flow = _series_for_periods(cashflow, ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities"), cf_periods)
            operating_cash_flow["TTM"] = _quarterly_ttm(q_cashflow, ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities")) or _safe_float(info.get("operatingCashflow"))

            capex = _series_for_periods(cashflow, ("Capital Expenditure",), cf_periods)
            capex["TTM"] = _quarterly_ttm(q_cashflow, ("Capital Expenditure",))
            if capex.get("TTM") is not None and capex["TTM"] > 0:
                capex["TTM"] = -abs(capex["TTM"])
            for period_label in PERIOD_LABELS[1:]:
                if capex.get(period_label) is not None and capex[period_label] > 0:
                    capex[period_label] = -abs(capex[period_label])

            free_cash_flow = _series_for_periods(cashflow, ("Free Cash Flow",), cf_periods)
            free_cash_flow["TTM"] = _quarterly_ttm(q_cashflow, ("Free Cash Flow",)) or _safe_float(info.get("freeCashflow"))
            if free_cash_flow.get("TTM") is None and operating_cash_flow.get("TTM") is not None and capex.get("TTM") is not None:
                free_cash_flow["TTM"] = operating_cash_flow["TTM"] + capex["TTM"]

            fcf_margin = _margin_series(free_cash_flow, revenue)
            fcf_growth = _growth_series(free_cash_flow)
            fcf_conversion = _fcf_conversion(free_cash_flow, net_income)

            snapshot = FinancialSnapshot(
                company=info.get("longName") or info.get("shortName") or label,
                ticker=ticker.upper(),
                currency=currency,
                fiscal_periods=fiscal_periods,
                performance={
                    "revenue": revenue,
                    "revenue_growth": revenue_growth,
                    "gross_profit": gross_profit,
                    "gross_margin": gross_margin,
                    "operating_income": operating_income,
                    "operating_margin": operating_margin,
                    "ebitda": ebitda,
                    "ebitda_margin": ebitda_margin,
                    "net_income": net_income,
                    "eps": eps,
                    "eps_growth": eps_growth,
                },
                health={
                    "cash": cash,
                    "debt": debt,
                    "net_debt": net_debt,
                    "current_assets": current_assets,
                    "current_liabilities": current_liabilities,
                    "working_capital": working_capital,
                    "equity": equity,
                    "debt_to_equity": debt_to_equity,
                    "debt_to_assets": debt_to_assets,
                },
                cash_flow={
                    "operating_cash_flow": operating_cash_flow,
                    "capex": capex,
                    "free_cash_flow": free_cash_flow,
                    "fcf_margin": fcf_margin,
                    "fcf_growth": fcf_growth,
                    "fcf_conversion": fcf_conversion,
                },
                status="Live",
                observed_at=observed,
                notes=[
                    "TTM aggregates the latest four reported quarters where available; balance-sheet items use the latest quarter.",
                    "FY-1 is the most recent full fiscal year; FY-2 through FY-4 are prior years.",
                ],
            )
            impact = _financial_impact(snapshot)
            findings = self._findings_from_snapshot(snapshot, impact)
            return snapshot, findings
        except Exception as exc:
            snapshot = FinancialSnapshot(
                company=label,
                ticker=ticker.upper(),
                currency="",
                status="Unavailable",
                observed_at=observed,
                notes=[f"Financial retrieval failed: {type(exc).__name__}."],
            )
            finding = AgentFinding(
                self.name,
                "Unavailable",
                observed,
                f"Financial statements could not be retrieved ({type(exc).__name__}).",
                SOURCE,
                f"https://finance.yahoo.com/quote/{ticker.upper()}/financials",
                impact="Unclear",
            )
            return snapshot, [finding]

    def _findings_from_snapshot(self, snapshot: FinancialSnapshot, impact: str) -> List[Any]:
        from .agents import AgentFinding
        perf = snapshot.performance
        health = snapshot.health
        cf = snapshot.cash_flow
        currency = snapshot.currency
        url = f"https://finance.yahoo.com/quote/{snapshot.ticker}/financials"

        def summary(label: str, values: Dict[str, Optional[float]], kind: str = "money") -> str:
            ttm = values.get("TTM")
            fy1 = values.get("FY-1")
            if kind == "pct":
                return f"{label}: TTM {_format_pct(ttm)}; FY-1 {_format_pct(fy1)}."
            if kind == "eps":
                return f"{label}: TTM {'N/A' if ttm is None else f'{ttm:.2f}'}; FY-1 {'N/A' if fy1 is None else f'{fy1:.2f}'}."
            return f"{label}: TTM {_format_large(ttm, currency)}; FY-1 {_format_large(fy1, currency)}."

        return [
            AgentFinding(
                self.name,
                "Live",
                snapshot.observed_at,
                summary("Revenue", perf.get("revenue", {})) + " " + summary("Revenue growth", perf.get("revenue_growth", {}), "pct"),
                SOURCE,
                url,
                impact,
            ),
            AgentFinding(
                self.name,
                "Live",
                snapshot.observed_at,
                summary("Gross margin", perf.get("gross_margin", {}), "pct")
                + " "
                + summary("Operating margin", perf.get("operating_margin", {}), "pct")
                + " "
                + summary("EBITDA margin", perf.get("ebitda_margin", {}), "pct"),
                SOURCE,
                url,
                impact,
            ),
            AgentFinding(
                self.name,
                "Live",
                snapshot.observed_at,
                summary("Net income", perf.get("net_income", {}))
                + " "
                + summary("EPS", perf.get("eps", {}), "eps")
                + " "
                + summary("EPS growth", perf.get("eps_growth", {}), "pct"),
                SOURCE,
                url,
                impact,
            ),
            AgentFinding(
                self.name,
                "Live",
                snapshot.observed_at,
                summary("Cash", health.get("cash", {}))
                + " "
                + summary("Debt", health.get("debt", {}))
                + " "
                + summary("Net debt", health.get("net_debt", {}))
                + " "
                + summary("Working capital", health.get("working_capital", {})),
                SOURCE,
                url,
                impact,
            ),
            AgentFinding(
                self.name,
                "Live",
                snapshot.observed_at,
                summary("Operating cash flow", cf.get("operating_cash_flow", {}))
                + " "
                + summary("CapEx", cf.get("capex", {}))
                + " "
                + summary("Free cash flow", cf.get("free_cash_flow", {}))
                + " "
                + summary("FCF margin", cf.get("fcf_margin", {}), "pct")
                + " "
                + summary("FCF conversion", cf.get("fcf_conversion", {}), "pct"),
                SOURCE,
                url,
                impact,
            ),
        ]
