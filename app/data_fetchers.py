"""Data fetchers for trigger evaluation."""

from __future__ import annotations

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import yfinance as yf

from .agents import USER_AGENT, _now, _request


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class YahooFinanceFetcher:
    """Fetch financial metrics and price data from Yahoo Finance."""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
    
    def fetch_financials(self, ticker: str) -> Dict[str, Any]:
        """Fetch financial statements and compute key metrics."""
        if not ticker or ticker == "—":
            return {"error": "No ticker available"}
        
        try:
            stock = yf.Ticker(ticker.upper())
            
            income = stock.financials
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            q_income = stock.quarterly_financials
            q_balance = stock.quarterly_balance_sheet
            q_cashflow = stock.quarterly_cashflow
            info = stock.info or {}
            
            result = {
                "ticker": ticker.upper(),
                "company": info.get("longName") or info.get("shortName") or ticker,
                "currency": info.get("currency") or info.get("financialCurrency") or "USD",
                "metrics": {},
                "quarterly_metrics": [],
                "fetched_at": _now(),
            }
            
            if income is not None and not income.empty:
                annual_periods = list(income.columns[:4])
                
                def get_row(df, *names):
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
                
                def get_quarterly_ttm(q_df, *names):
                    row = get_row(q_df, *names)
                    if row is None:
                        return None
                    values = [_safe_float(v) for v in row.iloc[:4]]
                    if any(v is None for v in values):
                        return None
                    return sum(v for v in values if v is not None)
                
                revenue_annual = {}
                revenue_row = get_row(income, "Total Revenue", "Operating Revenue")
                if revenue_row is not None:
                    for i, period in enumerate(annual_periods):
                        revenue_annual[f"FY-{i+1}"] = _safe_float(revenue_row.get(period))
                revenue_ttm = get_quarterly_ttm(q_income, "Total Revenue", "Operating Revenue") or _safe_float(info.get("totalRevenue"))
                if revenue_ttm is not None:
                    revenue_annual["TTM"] = revenue_ttm
                
                gross_profit_annual = {}
                gp_row = get_row(income, "Gross Profit")
                if gp_row is not None:
                    for i, period in enumerate(annual_periods):
                        gross_profit_annual[f"FY-{i+1}"] = _safe_float(gp_row.get(period))
                gp_ttm = get_quarterly_ttm(q_income, "Gross Profit")
                if gp_ttm is not None:
                    gross_profit_annual["TTM"] = gp_ttm
                
                op_income_annual = {}
                oi_row = get_row(income, "Operating Income", "EBIT")
                if oi_row is not None:
                    for i, period in enumerate(annual_periods):
                        op_income_annual[f"FY-{i+1}"] = _safe_float(oi_row.get(period))
                oi_ttm = get_quarterly_ttm(q_income, "Operating Income", "EBIT")
                if oi_ttm is not None:
                    op_income_annual["TTM"] = oi_ttm
                
                ebitda_annual = {}
                eb_row = get_row(income, "EBITDA", "Normalized EBITDA")
                if eb_row is not None:
                    for i, period in enumerate(annual_periods):
                        ebitda_annual[f"FY-{i+1}"] = _safe_float(eb_row.get(period))
                eb_ttm = get_quarterly_ttm(q_income, "EBITDA", "Normalized EBITDA") or _safe_float(info.get("ebitda"))
                if eb_ttm is not None:
                    ebitda_annual["TTM"] = eb_ttm
                
                net_income_annual = {}
                ni_row = get_row(income, "Net Income", "Net Income Common Stockholders")
                if ni_row is not None:
                    for i, period in enumerate(annual_periods):
                        net_income_annual[f"FY-{i+1}"] = _safe_float(ni_row.get(period))
                ni_ttm = get_quarterly_ttm(q_income, "Net Income", "Net Income Common Stockholders") or _safe_float(info.get("netIncomeToCommon"))
                if ni_ttm is not None:
                    net_income_annual["TTM"] = ni_ttm
                
                eps_annual = {}
                eps_row = get_row(income, "Diluted EPS", "Basic EPS")
                if eps_row is not None:
                    for i, period in enumerate(annual_periods):
                        eps_annual[f"FY-{i+1}"] = _safe_float(eps_row.get(period))
                eps_ttm = _safe_float(info.get("trailingEps"))
                if eps_ttm is not None:
                    eps_annual["TTM"] = eps_ttm
                
                balance_periods = list(balance.columns[:4]) if balance is not None else []
                
                cash_annual = {}
                cash_row = get_row(balance, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
                if cash_row is not None:
                    for i, period in enumerate(balance_periods):
                        cash_annual[f"FY-{i+1}"] = _safe_float(cash_row.get(period))
                if q_balance is not None:
                    latest_q = q_balance.columns[0]
                    row = get_row(q_balance, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
                    if row is not None:
                        cash_annual["TTM"] = _safe_float(row.get(latest_q))
                cash_annual["TTM"] = cash_annual.get("TTM") or _safe_float(info.get("totalCash"))
                
                debt_annual = {}
                debt_row = get_row(balance, "Total Debt")
                if debt_row is not None:
                    for i, period in enumerate(balance_periods):
                        debt_annual[f"FY-{i+1}"] = _safe_float(debt_row.get(period))
                if q_balance is not None:
                    latest_q = q_balance.columns[0]
                    row = get_row(q_balance, "Total Debt")
                    if row is not None:
                        debt_annual["TTM"] = _safe_float(row.get(latest_q))
                debt_annual["TTM"] = debt_annual.get("TTM") or _safe_float(info.get("totalDebt"))
                
                equity_annual = {}
                eq_row = get_row(balance, "Stockholders Equity", "Total Equity Gross Minority Interest")
                if eq_row is not None:
                    for i, period in enumerate(balance_periods):
                        equity_annual[f"FY-{i+1}"] = _safe_float(eq_row.get(period))
                
                assets_annual = {}
                ta_row = get_row(balance, "Total Assets")
                if ta_row is not None:
                    for i, period in enumerate(balance_periods):
                        assets_annual[f"FY-{i+1}"] = _safe_float(ta_row.get(period))
                
                current_assets_annual = {}
                ca_row = get_row(balance, "Current Assets", "Total Current Assets")
                if ca_row is not None:
                    for i, period in enumerate(balance_periods):
                        current_assets_annual[f"FY-{i+1}"] = _safe_float(ca_row.get(period))
                
                current_liabilities_annual = {}
                cl_row = get_row(balance, "Current Liabilities", "Total Current Liabilities")
                if cl_row is not None:
                    for i, period in enumerate(balance_periods):
                        current_liabilities_annual[f"FY-{i+1}"] = _safe_float(cl_row.get(period))
                
                cf_periods = list(cashflow.columns[:4]) if cashflow is not None else []
                
                ocf_annual = {}
                ocf_row = get_row(cashflow, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
                if ocf_row is not None:
                    for i, period in enumerate(cf_periods):
                        ocf_annual[f"FY-{i+1}"] = _safe_float(ocf_row.get(period))
                ocf_ttm = get_quarterly_ttm(q_cashflow, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities") or _safe_float(info.get("operatingCashflow"))
                if ocf_ttm is not None:
                    ocf_annual["TTM"] = ocf_ttm
                
                capex_annual = {}
                cx_row = get_row(cashflow, "Capital Expenditure")
                if cx_row is not None:
                    for i, period in enumerate(cf_periods):
                        val = _safe_float(cx_row.get(period))
                        if val is not None and val > 0:
                            val = -abs(val)
                        capex_annual[f"FY-{i+1}"] = val
                capex_ttm = get_quarterly_ttm(q_cashflow, "Capital Expenditure")
                if capex_ttm is not None and capex_ttm > 0:
                    capex_ttm = -abs(capex_ttm)
                if capex_ttm is not None:
                    capex_annual["TTM"] = capex_ttm
                
                fcf_annual = {}
                fcf_row = get_row(cashflow, "Free Cash Flow")
                if fcf_row is not None:
                    for i, period in enumerate(cf_periods):
                        fcf_annual[f"FY-{i+1}"] = _safe_float(fcf_row.get(period))
                fcf_ttm = get_quarterly_ttm(q_cashflow, "Free Cash Flow") or _safe_float(info.get("freeCashflow"))
                if fcf_ttm is None and ocf_ttm is not None and capex_ttm is not None:
                    fcf_ttm = ocf_ttm + capex_ttm
                if fcf_ttm is not None:
                    fcf_annual["TTM"] = fcf_ttm
                
                def compute_margin(num: Dict, den: Dict) -> Dict:
                    result = {}
                    for k in num:
                        if num[k] is not None and den.get(k) not in (None, 0):
                            result[k] = round(num[k] / den[k] * 100, 2)
                    return result
                
                def compute_growth(current: Dict, prior: Dict) -> Dict:
                    result = {}
                    for k in current:
                        if current[k] is not None and prior.get(k) not in (None, 0):
                            result[k] = round((current[k] - prior[k]) / abs(prior[k]) * 100, 2)
                    return result
                
                def compute_ratio(num: Dict, den: Dict) -> Dict:
                    result = {}
                    for k in num:
                        if num[k] is not None and den.get(k) not in (None, 0):
                            result[k] = round(num[k] / den[k], 2)
                    return result
                
                revenue = revenue_annual
                gross_profit = gross_profit_annual
                op_income = op_income_annual
                ebitda = ebitda_annual
                net_income = net_income_annual
                eps = eps_annual
                cash = cash_annual
                debt = debt_annual
                equity = equity_annual
                assets = assets_annual
                current_assets = current_assets_annual
                current_liabilities = current_liabilities_annual
                ocf = ocf_annual
                capex = capex_annual
                fcf = fcf_annual
                
                gross_margin = compute_margin(gross_profit, revenue)
                op_margin = compute_margin(op_income, revenue)
                ebitda_margin = compute_margin(ebitda, revenue)
                revenue_growth = compute_growth(revenue, {k: v for k, v in revenue.items() if k != "TTM"})
                eps_growth = compute_growth(eps, {k: v for k, v in eps.items() if k != "TTM"})
                
                net_debt = {}
                for k in cash:
                    c = cash.get(k)
                    d = debt.get(k)
                    if c is not None and d is not None:
                        net_debt[k] = d - c
                
                working_capital = {}
                for k in current_assets:
                    ca = current_assets.get(k)
                    cl = current_liabilities.get(k)
                    if ca is not None and cl is not None:
                        working_capital[k] = ca - cl
                
                debt_to_equity = compute_ratio(debt, equity)
                debt_to_assets = compute_ratio(debt, assets)
                
                fcf_margin = compute_margin(fcf, revenue)
                fcf_growth = compute_growth(fcf, {k: v for k, v in fcf.items() if k != "TTM"})
                fcf_conversion = {}
                for k in fcf:
                    if fcf[k] is not None and net_income.get(k) not in (None, 0):
                        fcf_conversion[k] = round(fcf[k] / net_income[k] * 100, 2)
                
                result["metrics"] = {
                    "revenue_growth_ttm": revenue_growth.get("TTM"),
                    "operating_margin_ttm": op_margin.get("TTM"),
                    "gross_margin_ttm": gross_margin.get("TTM"),
                    "net_debt_ttm": net_debt.get("TTM"),
                    "fcf_ttm": fcf.get("TTM"),
                    "eps_ttm": eps.get("TTM"),
                    "debt_to_equity_ttm": debt_to_equity.get("TTM"),
                    "debt_to_assets_ttm": debt_to_assets.get("TTM"),
                    "revenue_ttm": revenue.get("TTM"),
                    "operating_income_ttm": op_income.get("TTM"),
                    "net_income_ttm": net_income.get("TTM"),
                    "cash_ttm": cash.get("TTM"),
                    "working_capital_ttm": working_capital.get("TTM"),
                    "ebitda_margin_ttm": ebitda_margin.get("TTM"),
                    "fcf_margin_ttm": fcf_margin.get("TTM"),
                    "fcf_conversion_ttm": fcf_conversion.get("TTM"),
                }
                
                result["quarterly_metrics"] = []
                quarterly_periods = list(q_income.columns[:8]) if q_income is not None else []
                for period in quarterly_periods:
                    q_rev = _safe_float(get_row(q_income, "Total Revenue", "Operating Revenue").get(period)) if get_row(q_income, "Total Revenue", "Operating Revenue") is not None else None
                    q_ni = _safe_float(get_row(q_income, "Net Income", "Net Income Common Stockholders").get(period)) if get_row(q_income, "Net Income", "Net Income Common Stockholders") is not None else None
                    q_eps = _safe_float(get_row(q_income, "Diluted EPS", "Basic EPS").get(period)) if get_row(q_income, "Diluted EPS", "Basic EPS") is not None else None
                    if q_rev is not None or q_ni is not None or q_eps is not None:
                        result["quarterly_metrics"].append({
                            "period": str(period),
                            "revenue": q_rev,
                            "net_income": q_ni,
                            "eps": q_eps,
                        })
            
            return result
            
        except Exception as e:
            return {"error": f"Financial fetch failed: {type(e).__name__}: {e}"}
    
    def fetch_price(self, ticker: str) -> Dict[str, Any]:
        """Fetch current price and previous close."""
        if not ticker or ticker == "—":
            return {"error": "No ticker available"}
        
        try:
            response = _request(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_plus(ticker)}",
                {"range": "5d", "interval": "1d"}
            )
            response.raise_for_status()
            meta = response.json()["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            previous = meta.get("chartPreviousClose") or meta.get("previousClose")
            if price is None:
                return {"error": "No price data"}
            return {
                "ticker": ticker.upper(),
                "price": price,
                "previous_close": previous,
                "change_percent": ((price - previous) / previous * 100) if previous else None,
                "currency": meta.get("currency"),
                "fetched_at": _now(),
            }
        except Exception as e:
            return {"error": f"Price fetch failed: {type(e).__name__}: {e}"}
    
    def fetch_historical_metric(
        self, 
        ticker: str, 
        metric_name: str, 
        lookback: int = 8,
        period_type: str = "quarterly"
    ) -> List[float]:
        """Fetch historical values for a specific metric."""
        financials = self.fetch_financials(ticker)
        if "error" in financials:
            return []
        
        metrics = financials.get("metrics", {})
        quarterly = financials.get("quarterly_metrics", [])
        
        if metric_name in metrics:
            val = metrics[metric_name]
            if val is not None:
                return [val]
        
        if period_type == "quarterly" and quarterly:
            values = []
            for q in quarterly[:lookback]:
                if metric_name == "revenue_growth_ttm" and q.get("revenue") is not None:
                    pass
                elif metric_name in q:
                    val = q[metric_name]
                    if val is not None:
                        values.append(val)
            return values
        
        return []


class RSSFetcher:
    """Fetch news headlines from RSS feeds."""
    
    def __init__(self):
        self.cache: Dict[str, List[Dict]] = {}
    
    def fetch_google_news(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch headlines from Google News RSS."""
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        try:
            response = _request(url)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            items = []
            for item in root.findall("./channel/item")[:limit]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                items.append({
                    "title": title,
                    "url": link,
                    "source": "Google News RSS",
                    "published": pub_date,
                    "observed_at": _now(),
                    "impact": self._classify_impact(title),
                })
            return items
        except Exception as e:
            return [{"error": f"Google News fetch failed: {type(e).__name__}: {e}"}]
    
    def fetch_yahoo_rss(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch headlines from Yahoo Finance RSS for a ticker."""
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(ticker)}&region=US&lang=en-US"
        try:
            response = _request(url)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            items = []
            for item in root.findall("./channel/item")[:limit]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                items.append({
                    "title": title,
                    "url": link,
                    "source": "Yahoo Finance RSS",
                    "published": pub_date,
                    "observed_at": _now(),
                    "impact": self._classify_impact(title),
                })
            return items
        except Exception as e:
            return [{"error": f"Yahoo RSS fetch failed: {type(e).__name__}: {e}"}]
    
    def _classify_impact(self, text: str) -> str:
        lower = text.lower()
        negative = ("fall", "loss", "debt", "delay", "cut", "penalty", "downgrade", "risk", "probe", "investigation", "lawsuit", "bankruptcy", "default")
        positive = ("gain", "growth", "funding", "profit", "rise", "approval", "upgrade", "partnership", "launch", "acquisition", "merger", "beat", "exceed")
        if any(term in lower for term in negative):
            return "Negative"
        if any(term in lower for term in positive):
            return "Positive"
        return "Neutral"
    
    def fetch_company_news(self, company: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch company-specific news."""
        query = f'"{company}" stock'
        return self.fetch_google_news(query, limit)
    
    def fetch_competitor_news(self, competitors: List[str], industry: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch competitor news."""
        if not competitors:
            return []
        query = " OR ".join(f'"{c}"' for c in competitors) + f" {industry}"
        return self.fetch_google_news(query, limit)
    
    def fetch_regulatory_news(self, company: str, industry: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch regulatory/policy news."""
        query = f'"{company}" {industry} regulation policy'
        return self.fetch_google_news(query, limit)


def get_fetcher(data_source: str):
    """Get the appropriate fetcher for a data source."""
    if data_source == "yahoo_finance_financials":
        return YahooFinanceFetcher()
    elif data_source in ("google_news_rss", "yahoo_finance_rss"):
        return RSSFetcher()
    elif data_source == "yahoo_finance_price":
        return YahooFinanceFetcher()
    else:
        raise ValueError(f"Unknown data source: {data_source}")