"""Trigger condition parsing, validation, and evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .models import Trigger, TriggerCondition


FINANCIAL_METRICS = {
    "revenue_growth_ttm": {"unit": "percent", "source": "yahoo_finance_financials"},
    "operating_margin_ttm": {"unit": "percent", "source": "yahoo_finance_financials"},
    "gross_margin_ttm": {"unit": "percent", "source": "yahoo_finance_financials"},
    "net_debt_ttm": {"unit": "absolute", "source": "yahoo_finance_financials"},
    "fcf_ttm": {"unit": "absolute", "source": "yahoo_finance_financials"},
    "eps_ttm": {"unit": "absolute", "source": "yahoo_finance_financials"},
    "debt_to_equity_ttm": {"unit": "ratio", "source": "yahoo_finance_financials"},
    "debt_to_assets_ttm": {"unit": "ratio", "source": "yahoo_finance_financials"},
    "revenue_ttm": {"unit": "absolute", "source": "yahoo_finance_financials"},
    "operating_income_ttm": {"unit": "absolute", "source": "yahoo_finance_financials"},
    "net_income_ttm": {"unit": "absolute", "source": "yahoo_finance_financials"},
    "cash_ttm": {"unit": "absolute", "source": "yahoo_finance_financials"},
    "working_capital_ttm": {"unit": "absolute", "source": "yahoo_finance_financials"},
    "ebitda_margin_ttm": {"unit": "percent", "source": "yahoo_finance_financials"},
    "fcf_margin_ttm": {"unit": "percent", "source": "yahoo_finance_financials"},
    "fcf_conversion_ttm": {"unit": "percent", "source": "yahoo_finance_financials"},
}


def parse_condition(condition_dict: Dict[str, Any]) -> TriggerCondition:
    """Parse and validate a condition dictionary from LLM output."""
    condition_type = condition_dict.get("condition_type", "financial_metric")
    
    base = TriggerCondition(
        trigger_id="",
        condition_type=condition_type,
        data_source=condition_dict.get("data_source", "yahoo_finance_financials"),
    )
    
    if condition_type == "financial_metric":
        metric_name = condition_dict.get("metric_name")
        if not metric_name:
            raise ValueError("financial_metric requires metric_name")
        base.metric_name = metric_name
        base.operator = condition_dict.get("operator", "<")
        base.threshold = float(condition_dict.get("threshold", 0))
        base.unit = condition_dict.get("unit", "percent")
        base.lookback_periods = int(condition_dict.get("lookback_periods", 1))
        base.period_type = condition_dict.get("period_type", "quarterly")
        base.consecutive = bool(condition_dict.get("consecutive", False))
        base.allow_gaps = bool(condition_dict.get("allow_gaps", True))
        
    elif condition_type == "news_keyword":
        base.keywords = condition_dict.get("keywords", [])
        if not base.keywords:
            raise ValueError("news_keyword requires keywords list")
        base.lookback_periods = int(condition_dict.get("lookback_periods", 7))
        base.threshold = float(condition_dict.get("threshold", 1))
        base.unit = "count"
        
    elif condition_type == "news_sentiment":
        base.sentiment_threshold = float(condition_dict.get("sentiment_threshold", -0.3))
        base.lookback_periods = int(condition_dict.get("lookback_periods", 7))
        base.threshold = float(condition_dict.get("threshold", 3))
        base.unit = "count"
        
    elif condition_type == "news_volume":
        base.volume_multiplier = float(condition_dict.get("volume_multiplier", 2.0))
        base.lookback_periods = int(condition_dict.get("lookback_periods", 30))
        base.threshold = float(condition_dict.get("threshold", 5))
        base.unit = "count"
        
    elif condition_type == "price_change":
        base.metric_name = condition_dict.get("metric_name", "price_change_pct")
        base.operator = condition_dict.get("operator", "<")
        base.threshold = float(condition_dict.get("threshold", 0))
        base.unit = "percent"
        base.lookback_periods = int(condition_dict.get("lookback_periods", 1))
        
    else:
        raise ValueError(f"Unknown condition_type: {condition_type}")
    
    return base


def validate_condition(condition: TriggerCondition) -> List[str]:
    """Validate a trigger condition, return list of errors (empty if valid)."""
    errors = []
    
    if condition.condition_type == "financial_metric":
        if not condition.metric_name:
            errors.append("financial_metric requires metric_name")
        elif condition.metric_name not in FINANCIAL_METRICS:
            errors.append(f"Unknown financial metric: {condition.metric_name}")
        if condition.operator not in ("<", ">", "<=", ">=", "==", "!="):
            errors.append(f"Invalid operator: {condition.operator}")
        if condition.threshold is None:
            errors.append("financial_metric requires threshold")
        if condition.lookback_periods < 1:
            errors.append("lookback_periods must be >= 1")
            
    elif condition.condition_type == "news_keyword":
        if not condition.keywords:
            errors.append("news_keyword requires keywords list")
        if condition.lookback_periods < 1:
            errors.append("lookback_periods must be >= 1")
            
    elif condition.condition_type == "news_sentiment":
        if condition.sentiment_threshold is None:
            errors.append("news_sentiment requires sentiment_threshold")
        elif not -1 <= condition.sentiment_threshold <= 1:
            errors.append("sentiment_threshold must be between -1 and 1")
        if condition.lookback_periods < 1:
            errors.append("lookback_periods must be >= 1")
            
    elif condition.condition_type == "news_volume":
        if condition.volume_multiplier is None or condition.volume_multiplier <= 1:
            errors.append("news_volume requires volume_multiplier > 1")
        if condition.lookback_periods < 1:
            errors.append("lookback_periods must be >= 1")
            
    elif condition.condition_type == "price_change":
        if condition.operator not in ("<", ">", "<=", ">=", "==", "!="):
            errors.append(f"Invalid operator: {condition.operator}")
        if condition.threshold is None:
            errors.append("price_change requires threshold")
            
    return errors


def condition_to_dict(condition: TriggerCondition) -> Dict[str, Any]:
    """Convert TriggerCondition to dictionary for storage."""
    return asdict(condition)


def dict_to_condition(data: Dict[str, Any]) -> TriggerCondition:
    """Convert dictionary to TriggerCondition."""
    return TriggerCondition(**{k: v for k, v in data.items() if k in TriggerCondition.__annotations__})


def evaluate_financial_condition(
    condition: TriggerCondition,
    historical_values: List[float],
    current_value: float
) -> Tuple[bool, str]:
    """Evaluate a financial metric condition against historical values."""
    if not historical_values:
        return False, "No historical data available"
    
    op = condition.operator
    threshold = condition.threshold
    
    def check(val: float) -> bool:
        if op == "<":
            return val < threshold
        elif op == ">":
            return val > threshold
        elif op == "<=":
            return val <= threshold
        elif op == ">=":
            return val >= threshold
        elif op == "==":
            return val == threshold
        elif op == "!=":
            return val != threshold
        return False
    
    if condition.consecutive:
        if len(historical_values) < condition.lookback_periods:
            return False, f"Need {condition.lookback_periods} periods, have {len(historical_values)}"
        recent = historical_values[:condition.lookback_periods]
        all_met = all(check(v) for v in recent)
        details = f"Last {len(recent)} periods: {recent}, all {'met' if all_met else 'not met'} condition {op} {threshold}"
        return all_met, details
    else:
        latest = historical_values[0]
        met = check(latest)
        details = f"Latest value: {latest}, condition {op} {threshold} {'met' if met else 'not met'}"
        return met, details


def evaluate_news_keyword_condition(
    condition: TriggerCondition,
    headlines: List[Dict[str, Any]],
    since_days: int
) -> Tuple[bool, str]:
    """Evaluate news keyword condition."""
    if not condition.keywords:
        return False, "No keywords specified"
    
    cutoff = datetime.now() - timedelta(days=since_days)
    matching = []
    
    for h in headlines:
        h_date_str = h.get("observed_at", "")
        try:
            h_date = datetime.strptime(h_date_str, "%Y-%m-%d %H:%M:%S UTC")
            if h_date < cutoff:
                continue
        except Exception:
            continue
            
        title = h.get("finding", "").lower()
        for kw in condition.keywords:
            if kw.lower() in title:
                matching.append(h.get("finding", ""))
                break
    
    count = len(matching)
    met = count >= (condition.threshold or 1)
    details = f"Found {count} matching headlines (threshold: {condition.threshold or 1}) in last {since_days} days"
    if matching:
        details += f". Matches: {'; '.join(matching[:3])}"
    return met, details


def evaluate_news_sentiment_condition(
    condition: TriggerCondition,
    headlines: List[Dict[str, Any]],
    since_days: int
) -> Tuple[bool, str]:
    """Evaluate news sentiment condition."""
    cutoff = datetime.now() - timedelta(days=since_days)
    threshold = condition.sentiment_threshold or -0.3
    matching = []
    
    for h in headlines:
        h_date_str = h.get("observed_at", "")
        try:
            h_date = datetime.strptime(h_date_str, "%Y-%m-%d %H:%M:%S UTC")
            if h_date < cutoff:
                continue
        except Exception:
            continue
            
        impact = h.get("impact", "").lower()
        if impact == "negative" and threshold < 0:
            matching.append(h.get("finding", ""))
        elif impact == "positive" and threshold > 0:
            matching.append(h.get("finding", ""))
    
    count = len(matching)
    required = condition.threshold or 3
    met = count >= required
    details = f"Found {count} headlines with sentiment beyond {threshold} (threshold: {required}) in last {since_days} days"
    return met, details


def evaluate_news_volume_condition(
    condition: TriggerCondition,
    headlines: List[Dict[str, Any]],
    since_days: int
) -> Tuple[bool, str]:
    """Evaluate news volume spike condition."""
    cutoff = datetime.now() - timedelta(days=since_days)
    recent_count = 0
    
    for h in headlines:
        h_date_str = h.get("observed_at", "")
        try:
            h_date = datetime.strptime(h_date_str, "%Y-%m-%d %H:%M:%S UTC")
            if h_date >= cutoff:
                recent_count += 1
        except Exception:
            continue
    
    baseline_days = condition.lookback_periods
    baseline_cutoff = datetime.now() - timedelta(days=baseline_days * 2)
    baseline_count = 0
    
    for h in headlines:
        h_date_str = h.get("observed_at", "")
        try:
            h_date = datetime.strptime(h_date_str, "%Y-%m-%d %H:%M:%S UTC")
            if baseline_cutoff <= h_date < cutoff:
                baseline_count += 1
        except Exception:
            continue
    
    baseline_avg = baseline_count / baseline_days if baseline_days > 0 else 0
    expected = baseline_avg * (condition.volume_multiplier or 2.0)
    min_threshold = condition.threshold or 5
    
    met = recent_count >= max(expected, min_threshold)
    details = f"Recent: {recent_count} headlines in {since_days} days, baseline avg: {baseline_avg:.1f}/day, expected >{expected:.1f} (min {min_threshold})"
    return met, details


def evaluate_price_condition(
    condition: TriggerCondition,
    current_price: float,
    previous_price: float
) -> Tuple[bool, str]:
    """Evaluate price change condition."""
    if previous_price == 0:
        return False, "Previous price is zero"
    
    change_pct = ((current_price - previous_price) / previous_price) * 100
    op = condition.operator
    threshold = condition.threshold or 0
    
    if op == "<":
        met = change_pct < threshold
    elif op == ">":
        met = change_pct > threshold
    elif op == "<=":
        met = change_pct <= threshold
    elif op == ">=":
        met = change_pct >= threshold
    elif op == "==":
        met = change_pct == threshold
    elif op == "!=":
        met = change_pct != threshold
    else:
        return False, f"Invalid operator: {op}"
    
    details = f"Price change: {change_pct:+.2f}%, condition {op} {threshold}% {'met' if met else 'not met'}"
    return met, details


def get_required_data_source(condition: TriggerCondition) -> str:
    """Get the data source required for a condition."""
    return condition.data_source


def frequency_to_scheduler_args(frequency: str) -> Dict[str, Any]:
    """Convert monitoring frequency to APScheduler arguments."""
    freq = frequency.lower()
    if freq == "hours":
        return {"trigger": "interval", "hours": 1}
    elif freq == "daily":
        return {"trigger": "cron", "hour": 6, "minute": 0}
    elif freq == "weekly":
        return {"trigger": "cron", "day_of_week": "mon", "hour": 6, "minute": 0}
    elif freq == "monthly":
        return {"trigger": "cron", "day": 1, "hour": 6, "minute": 0}
    else:
        return {"trigger": "interval", "hours": 1}