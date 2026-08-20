"""Trigger evaluation engine - evaluates conditions against live data."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .models import Trigger, TriggerCondition, TriggerEvaluation, MetricHistory
from .trigger_conditions import (
    parse_condition,
    validate_condition,
    evaluate_financial_condition,
    evaluate_news_keyword_condition,
    evaluate_news_sentiment_condition,
    evaluate_news_volume_condition,
    evaluate_price_condition,
    get_required_data_source,
)
from .data_fetchers import get_fetcher, YahooFinanceFetcher, RSSFetcher
from .store import _session, _normalize_company, TriggerState, MetricHistory as DBMetricHistory, TriggerEvaluation as DBTriggerEvaluation, TriggerCondition as DBTriggerCondition
from sqlalchemy import and_


class TriggerEvaluator:
    """Evaluates triggers against live data sources."""
    
    def __init__(self):
        self.yahoo_fetcher = YahooFinanceFetcher()
        self.rss_fetcher = RSSFetcher()
    
    def evaluate_trigger(
        self, 
        trigger: Trigger, 
        company: str, 
        ticker: str,
        competitors: List[str],
        industry: str
    ) -> TriggerEvaluation:
        """Evaluate a single trigger and return evaluation result."""
        if not trigger.condition:
            return TriggerEvaluation(
                trigger_id=trigger.trigger_id,
                evaluated_at=datetime.now(timezone.utc).isoformat(),
                condition_met=False,
                details="No condition defined for trigger",
                previous_status=trigger.status,
                new_status=trigger.status,
            )
        
        condition = trigger.condition
        try:
            if isinstance(condition, dict):
                condition = parse_condition(condition)
            
            errors = validate_condition(condition)
            if errors:
                return TriggerEvaluation(
                    trigger_id=trigger.trigger_id,
                    evaluated_at=datetime.now(timezone.utc).isoformat(),
                    condition_met=False,
                    details=f"Invalid condition: {'; '.join(errors)}",
                    previous_status=trigger.status,
                    new_status=trigger.status,
                )
            
            data_source = get_required_data_source(condition)
            fetcher = get_fetcher(data_source)
            
            if condition.condition_type == "financial_metric":
                return self._evaluate_financial(trigger, condition, ticker, company)
            elif condition.condition_type == "news_keyword":
                return self._evaluate_news_keyword(trigger, condition, company)
            elif condition.condition_type == "news_sentiment":
                return self._evaluate_news_sentiment(trigger, condition, company)
            elif condition.condition_type == "news_volume":
                return self._evaluate_news_volume(trigger, condition, company)
            elif condition.condition_type == "price_change":
                return self._evaluate_price_change(trigger, condition, ticker)
            else:
                return TriggerEvaluation(
                    trigger_id=trigger.trigger_id,
                    evaluated_at=datetime.now(timezone.utc).isoformat(),
                    condition_met=False,
                    details=f"Unknown condition type: {condition.condition_type}",
                    previous_status=trigger.status,
                    new_status=trigger.status,
                )
        except Exception as e:
            return TriggerEvaluation(
                trigger_id=trigger.trigger_id,
                evaluated_at=datetime.now(timezone.utc).isoformat(),
                condition_met=False,
                details=f"Evaluation error: {type(e).__name__}: {e}",
                previous_status=trigger.status,
                new_status=trigger.status,
            )
    
    def _evaluate_financial(
        self, 
        trigger: Trigger, 
        condition: TriggerCondition, 
        ticker: str,
        company: str
    ) -> TriggerEvaluation:
        """Evaluate financial metric condition."""
        financials = self.yahoo_fetcher.fetch_financials(ticker)
        
        if "error" in financials:
            return TriggerEvaluation(
                trigger_id=trigger.trigger_id,
                evaluated_at=datetime.now(timezone.utc).isoformat(),
                condition_met=False,
                details=f"Financial data unavailable: {financials['error']}",
                previous_status=trigger.status,
                new_status=trigger.status,
            )
        
        metrics = financials.get("metrics", {})
        metric_name = condition.metric_name
        
        current_value = metrics.get(metric_name)
        if current_value is None:
            quarterly = financials.get("quarterly_metrics", [])
            values = []
            for q in quarterly[:condition.lookback_periods]:
                if metric_name in q and q[metric_name] is not None:
                    values.append(q[metric_name])
            if values:
                current_value = values[0]
                historical = values
            else:
                return TriggerEvaluation(
                    trigger_id=trigger.trigger_id,
                    evaluated_at=datetime.now(timezone.utc).isoformat(),
                    condition_met=False,
                    details=f"Metric {metric_name} not found in financial data",
                    previous_status=trigger.status,
                    new_status=trigger.status,
                )
        else:
            historical = [current_value]
        
        self._store_metric_history(company, metric_name, historical, condition.period_type, "yahoo_finance_financials")
        
        met, details = evaluate_financial_condition(condition, historical, current_value)
        
        new_status = self._determine_new_status(trigger, met)
        
        return TriggerEvaluation(
            trigger_id=trigger.trigger_id,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            condition_met=met,
            current_value=current_value,
            threshold=condition.threshold,
            details=details,
            previous_status=trigger.status,
            new_status=new_status,
        )
    
    def _evaluate_news_keyword(
        self, 
        trigger: Trigger, 
        condition: TriggerCondition, 
        company: str
    ) -> TriggerEvaluation:
        """Evaluate news keyword condition."""
        headlines = self.rss_fetcher.fetch_company_news(company, limit=50)
        
        met, details = evaluate_news_keyword_condition(condition, headlines, condition.lookback_periods)
        new_status = self._determine_new_status(trigger, met)
        
        return TriggerEvaluation(
            trigger_id=trigger.trigger_id,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            condition_met=met,
            details=details,
            previous_status=trigger.status,
            new_status=new_status,
        )
    
    def _evaluate_news_sentiment(
        self, 
        trigger: Trigger, 
        condition: TriggerCondition, 
        company: str
    ) -> TriggerEvaluation:
        """Evaluate news sentiment condition."""
        headlines = self.rss_fetcher.fetch_company_news(company, limit=50)
        
        met, details = evaluate_news_sentiment_condition(condition, headlines, condition.lookback_periods)
        new_status = self._determine_new_status(trigger, met)
        
        return TriggerEvaluation(
            trigger_id=trigger.trigger_id,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            condition_met=met,
            details=details,
            previous_status=trigger.status,
            new_status=new_status,
        )
    
    def _evaluate_news_volume(
        self, 
        trigger: Trigger, 
        condition: TriggerCondition, 
        company: str
    ) -> TriggerEvaluation:
        """Evaluate news volume spike condition."""
        headlines = self.rss_fetcher.fetch_company_news(company, limit=100)
        
        met, details = evaluate_news_volume_condition(condition, headlines, condition.lookback_periods)
        new_status = self._determine_new_status(trigger, met)
        
        return TriggerEvaluation(
            trigger_id=trigger.trigger_id,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            condition_met=met,
            details=details,
            previous_status=trigger.status,
            new_status=new_status,
        )
    
    def _evaluate_price_change(
        self, 
        trigger: Trigger, 
        condition: TriggerCondition, 
        ticker: str
    ) -> TriggerEvaluation:
        """Evaluate price change condition."""
        price_data = self.yahoo_fetcher.fetch_price(ticker)
        
        if "error" in price_data:
            return TriggerEvaluation(
                trigger_id=trigger.trigger_id,
                evaluated_at=datetime.now(timezone.utc).isoformat(),
                condition_met=False,
                details=f"Price data unavailable: {price_data['error']}",
                previous_status=trigger.status,
                new_status=trigger.status,
            )
        
        current_price = price_data.get("price", 0)
        previous_price = price_data.get("previous_close", 0)
        
        met, details = evaluate_price_condition(condition, current_price, previous_price)
        new_status = self._determine_new_status(trigger, met)
        
        return TriggerEvaluation(
            trigger_id=trigger.trigger_id,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            condition_met=met,
            current_value=current_price,
            threshold=condition.threshold,
            details=details,
            previous_status=trigger.status,
            new_status=new_status,
        )
    
    def _determine_new_status(self, trigger: Trigger, condition_met: bool) -> str:
        """Determine new trigger status based on condition result and cooldown."""
        now = datetime.now(timezone.utc)
        
        if trigger.cooldown_until:
            try:
                cooldown = datetime.fromisoformat(trigger.cooldown_until.replace('Z', '+00:00'))
                if now < cooldown:
                    return trigger.status
            except Exception:
                pass
        
        current = trigger.status
        
        if condition_met:
            if current == "Monitoring":
                if trigger.category == "Negative":
                    return "Activated"
                elif trigger.category == "Positive":
                    return "Strengthened"
                else:
                    return "Activated"
            elif current in ("Activated", "Strengthened"):
                return current
        else:
            if current in ("Activated", "Strengthened"):
                return "Monitoring"
        
        return current
    
    def _store_metric_history(
        self, 
        company: str, 
        metric_name: str, 
        values: List[float], 
        period_type: str,
        source: str
    ) -> None:
        """Store metric values in history table."""
        session = _session()
        try:
            for i, value in enumerate(values):
                period_end = (datetime.now() - timedelta(days=i * 90)).strftime("%Y-%m-%d")
                exists = session.query(DBMetricHistory).filter_by(
                    company=company,
                    metric_name=metric_name,
                    period_end=period_end
                ).first()
                if not exists:
                    session.add(DBMetricHistory(
                        company=company,
                        metric_name=metric_name,
                        value=value,
                        period_end=period_end,
                        period_type=period_type,
                        source=source,
                    ))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    
    def evaluate_all_triggers(
        self, 
        triggers: List[Trigger], 
        company: str, 
        ticker: str,
        competitors: List[str],
        industry: str
    ) -> List[TriggerEvaluation]:
        """Evaluate all triggers for a company."""
        results = []
        for trigger in triggers:
            eval_result = self.evaluate_trigger(trigger, company, ticker, competitors, industry)
            results.append(eval_result)
            
            if eval_result.new_status != eval_result.previous_status:
                self._persist_evaluation(eval_result)
                self._update_trigger_status(trigger, eval_result.new_status)
        
        return results
    
    def _persist_evaluation(self, evaluation: TriggerEvaluation) -> None:
        """Persist evaluation result to database."""
        session = _session()
        try:
            session.add(DBTriggerEvaluation(
                trigger_id=evaluation.trigger_id,
                evaluated_at=evaluation.evaluated_at,
                condition_met=evaluation.condition_met,
                current_value=evaluation.current_value,
                threshold=evaluation.threshold,
                details=evaluation.details,
                alert_sent=evaluation.alert_sent,
                previous_status=evaluation.previous_status,
                new_status=evaluation.new_status,
            ))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    
    def _update_trigger_status(self, trigger: Trigger, new_status: str) -> None:
        """Update trigger status in database."""
        from .store import set_trigger_status
        set_trigger_status(trigger.trigger_id.split("-")[-1] if "-" in trigger.trigger_id else "", trigger.trigger_id, new_status)
        trigger.status = new_status
        
        if new_status in ("Activated", "Strengthened"):
            cooldown = datetime.now(timezone.utc) + timedelta(hours=24)
            trigger.cooldown_until = cooldown.isoformat()


def load_triggers_from_db(company: str) -> List[Trigger]:
    """Load triggers with conditions from database."""
    company = _normalize_company(company)
    session = _session()
    try:
        from .models import Trigger
        trigger_states = session.query(TriggerState).filter_by(company=company).all()
        triggers = []
        for ts in trigger_states:
            # Include main company in related_companies for tracking
            related_companies = company  # Will be joined with competitors when available
            trigger = Trigger(
                trigger_id=ts.trigger_id,
                category="",
                description="",
                confidence=0,
                importance="Medium",
                related_driver="",
                related_companies=related_companies,
                related_industry="",
                monitoring_frequency="Daily",
                status=ts.status,
            )
            triggers.append(trigger)
        return triggers
    finally:
        session.close()


def save_trigger_condition(trigger_id: str, condition: TriggerCondition) -> None:
    """Save trigger condition to database."""
    session = _session()
    try:
        existing = session.query(DBTriggerCondition).filter_by(trigger_id=trigger_id).first()
        if existing:
            for key, value in condition_to_dict(condition).items():
                setattr(existing, key, value)
        else:
            session.add(DBTriggerCondition(
                trigger_id=trigger_id,
                **condition_to_dict(condition)
            ))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def condition_to_dict(condition: TriggerCondition) -> Dict[str, Any]:
    """Convert TriggerCondition to dict for storage."""
    return {
        "trigger_id": condition.trigger_id,
        "condition_type": condition.condition_type,
        "metric_name": condition.metric_name,
        "operator": condition.operator,
        "threshold": condition.threshold,
        "unit": condition.unit,
        "lookback_periods": condition.lookback_periods,
        "period_type": condition.period_type,
        "consecutive": condition.consecutive,
        "allow_gaps": condition.allow_gaps,
        "keywords": condition.keywords,
        "sentiment_threshold": condition.sentiment_threshold,
        "volume_multiplier": condition.volume_multiplier,
        "data_source": condition.data_source,
    }


def get_trigger_condition(trigger_id: str) -> Optional[TriggerCondition]:
    """Load trigger condition from database."""
    session = _session()
    try:
        row = session.query(DBTriggerCondition).filter_by(trigger_id=trigger_id).first()
        if row:
            return TriggerCondition(
                trigger_id=row.trigger_id,
                condition_type=row.condition_type,
                metric_name=row.metric_name,
                operator=row.operator,
                threshold=row.threshold,
                unit=row.unit,
                lookback_periods=row.lookback_periods,
                period_type=row.period_type,
                consecutive=row.consecutive,
                allow_gaps=row.allow_gaps,
                keywords=row.keywords,
                sentiment_threshold=row.sentiment_threshold,
                volume_multiplier=row.volume_multiplier,
                data_source=row.data_source,
            )
        return None
    finally:
        session.close()