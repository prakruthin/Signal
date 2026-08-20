import json
import os
from datetime import datetime
from sqlalchemy import create_engine, String, Text, DateTime, Integer, Float, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ThesisVersion(Base):
    __tablename__ = "thesis_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(180), index=True)
    version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    company: Mapped[str] = mapped_column(String(180), index=True)
    trigger_id: Mapped[str] = mapped_column(String(80))
    trigger_status: Mapped[str] = mapped_column(String(80))
    delivery_status: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TriggerState(Base):
    __tablename__ = "trigger_states"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(180), index=True)
    trigger_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TriggerCondition(Base):
    __tablename__ = "trigger_conditions"
    id: Mapped[int] = mapped_column(primary_key=True)
    trigger_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    condition_type: Mapped[str] = mapped_column(String(50))
    metric_name: Mapped[str] = mapped_column(String(100), nullable=True)
    operator: Mapped[str] = mapped_column(String(10), nullable=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=True)
    lookback_periods: Mapped[int] = mapped_column(Integer, default=1)
    period_type: Mapped[str] = mapped_column(String(20), default="quarterly")
    consecutive: Mapped[bool] = mapped_column(default=False)
    allow_gaps: Mapped[bool] = mapped_column(default=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array
    sentiment_threshold: Mapped[float] = mapped_column(Float, nullable=True)
    volume_multiplier: Mapped[float] = mapped_column(Float, nullable=True)
    data_source: Mapped[str] = mapped_column(String(50))
    # Trigger metadata fields
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(20), nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, nullable=True)
    importance: Mapped[str] = mapped_column(String(20), nullable=True)
    related_driver: Mapped[str] = mapped_column(String(200), nullable=True)
    monitoring_frequency: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MetricHistory(Base):
    __tablename__ = "metric_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(180), index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    period_end: Mapped[str] = mapped_column(String(20), index=True)
    period_type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TriggerEvaluation(Base):
    __tablename__ = "trigger_evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    trigger_id: Mapped[str] = mapped_column(String(80), index=True)
    evaluated_at: Mapped[str] = mapped_column(String(50), index=True)
    condition_met: Mapped[bool] = mapped_column(default=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    alert_sent: Mapped[bool] = mapped_column(default=False)
    previous_status: Mapped[str] = mapped_column(String(80))
    new_status: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def _normalize_company(name: str) -> str:
    """Normalize company name for consistent storage/querying."""
    return name.strip() if name else name


def _session():
    url = os.getenv("DATABASE_URL", "sqlite:///investment_intelligence.db")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def save_thesis(company: str, summary: str, reason: str = "Initial analyst thesis") -> int:
    company = _normalize_company(company)
    session = _session()
    latest = session.query(ThesisVersion).filter_by(company=company).order_by(ThesisVersion.version.desc()).first()
    item = ThesisVersion(company=company, version=(latest.version + 1 if latest else 1), summary=summary, reason=reason)
    session.add(item); session.commit(); session.refresh(item); session.close()
    return item.version


def thesis_history(company: str):
    company = _normalize_company(company)
    session = _session()
    rows = session.query(ThesisVersion).filter_by(company=company).order_by(ThesisVersion.version.desc()).all()
    result = [[f"v{x.version}", x.reason, x.created_at.strftime("%Y-%m-%d %H:%M"), x.summary[:180] + "…"] for x in rows]
    session.close(); return result


def alert_was_sent(fingerprint: str) -> bool:
    session = _session()
    exists = session.query(AlertDelivery.id).filter_by(fingerprint=fingerprint).first() is not None
    session.close()
    return exists


def record_alert(fingerprint: str, company: str, trigger_id: str, trigger_status: str, delivery_status: str, subject: str):
    session = _session()
    session.add(AlertDelivery(fingerprint=fingerprint, company=company, trigger_id=trigger_id, trigger_status=trigger_status, delivery_status=delivery_status, subject=subject))
    session.commit(); session.close()


def trigger_status(company: str, trigger_id: str):
    company = _normalize_company(company)
    session = _session()
    row = session.query(TriggerState).filter_by(company=company, trigger_id=trigger_id).first()
    status = row.status if row else None
    session.close()
    return status


def set_trigger_status(company: str, trigger_id: str, status: str):
    company = _normalize_company(company)
    session = _session()
    row = session.query(TriggerState).filter_by(company=company, trigger_id=trigger_id).first()
    if row:
        row.status = status
    else:
        session.add(TriggerState(company=company, trigger_id=trigger_id, status=status))
    session.commit(); session.close()


def save_trigger_condition(trigger_id: str, condition: dict):
    """Save trigger condition to database."""
    session = _session()
    try:
        existing = session.query(TriggerCondition).filter_by(trigger_id=trigger_id).first()
        keywords_json = json.dumps(condition.get("keywords")) if condition.get("keywords") else None
        if existing:
            existing.condition_type = condition.get("condition_type")
            existing.metric_name = condition.get("metric_name")
            existing.operator = condition.get("operator")
            existing.threshold = condition.get("threshold")
            existing.unit = condition.get("unit")
            existing.lookback_periods = condition.get("lookback_periods", 1)
            existing.period_type = condition.get("period_type", "quarterly")
            existing.consecutive = condition.get("consecutive", False)
            existing.allow_gaps = condition.get("allow_gaps", True)
            existing.keywords = keywords_json
            existing.sentiment_threshold = condition.get("sentiment_threshold")
            existing.volume_multiplier = condition.get("volume_multiplier")
            existing.data_source = condition.get("data_source")
            # Trigger metadata
            existing.description = condition.get("description")
            existing.category = condition.get("category")
            existing.confidence = condition.get("confidence")
            existing.importance = condition.get("importance")
            existing.related_driver = condition.get("related_driver")
            existing.monitoring_frequency = condition.get("monitoring_frequency")
            existing.status = condition.get("status")
        else:
            session.add(TriggerCondition(
                trigger_id=trigger_id,
                condition_type=condition.get("condition_type"),
                metric_name=condition.get("metric_name"),
                operator=condition.get("operator"),
                threshold=condition.get("threshold"),
                unit=condition.get("unit"),
                lookback_periods=condition.get("lookback_periods", 1),
                period_type=condition.get("period_type", "quarterly"),
                consecutive=condition.get("consecutive", False),
                allow_gaps=condition.get("allow_gaps", True),
                keywords=keywords_json,
                sentiment_threshold=condition.get("sentiment_threshold"),
                volume_multiplier=condition.get("volume_multiplier"),
                data_source=condition.get("data_source"),
                # Trigger metadata
                description=condition.get("description"),
                category=condition.get("category"),
                confidence=condition.get("confidence"),
                importance=condition.get("importance"),
                related_driver=condition.get("related_driver"),
                monitoring_frequency=condition.get("monitoring_frequency"),
                status=condition.get("status"),
            ))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_trigger_condition(trigger_id: str) -> dict:
    """Load trigger condition from database."""
    session = _session()
    try:
        row = session.query(TriggerCondition).filter_by(trigger_id=trigger_id).first()
        if row:
            return {
                "trigger_id": row.trigger_id,
                "condition_type": row.condition_type,
                "metric_name": row.metric_name,
                "operator": row.operator,
                "threshold": row.threshold,
                "unit": row.unit,
                "lookback_periods": row.lookback_periods,
                "period_type": row.period_type,
                "consecutive": row.consecutive,
                "allow_gaps": row.allow_gaps,
                "keywords": json.loads(row.keywords) if row.keywords else None,
                "sentiment_threshold": row.sentiment_threshold,
                "volume_multiplier": row.volume_multiplier,
                "data_source": row.data_source,
                # Trigger metadata
                "description": row.description,
                "category": row.category,
                "confidence": row.confidence,
                "importance": row.importance,
                "related_driver": row.related_driver,
                "monitoring_frequency": row.monitoring_frequency,
                "status": row.status,
            }
        return {}
    finally:
        session.close()


def get_all_trigger_conditions(company: str) -> list:
    """Get all trigger conditions for a company (via trigger_states)."""
    company = _normalize_company(company)
    session = _session()
    try:
        trigger_ids = session.query(TriggerState.trigger_id).filter_by(company=company).all()
        conditions = []
        for (tid,) in trigger_ids:
            cond = get_trigger_condition(tid)
            if cond:
                conditions.append(cond)
        return conditions
    finally:
        session.close()


def get_all_companies_with_triggers() -> list:
    """Get list of all companies that have triggers in the database."""
    session = _session()
    try:
        companies = session.query(TriggerState.company).distinct().all()
        return [_normalize_company(c[0]) for c in companies]
    finally:
        session.close()


def get_all_trigger_states() -> list:
    """Get all trigger states across all companies."""
    session = _session()
    try:
        rows = session.query(TriggerState).order_by(TriggerState.company, TriggerState.trigger_id).all()
        return [{
            "company": r.company,
            "trigger_id": r.trigger_id,
            "status": r.status,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        } for r in rows]
    finally:
        session.close()


def store_metric_history(company: str, metric_name: str, value: float, period_end: str, period_type: str, source: str):
    """Store a metric value in history."""
    session = _session()
    try:
        exists = session.query(MetricHistory).filter_by(
            company=company, metric_name=metric_name, period_end=period_end
        ).first()
        if not exists:
            session.add(MetricHistory(
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


def get_metric_history(company: str, metric_name: str, limit: int = 8) -> list:
    """Get historical values for a metric."""
    session = _session()
    try:
        rows = session.query(MetricHistory).filter_by(
            company=company, metric_name=metric_name
        ).order_by(MetricHistory.period_end.desc()).limit(limit).all()
        return [{"value": r.value, "period_end": r.period_end, "period_type": r.period_type, "source": r.source} for r in rows]
    finally:
        session.close()


def log_trigger_evaluation(evaluation: dict):
    """Log a trigger evaluation result."""
    session = _session()
    try:
        session.add(TriggerEvaluation(
            trigger_id=evaluation.get("trigger_id"),
            evaluated_at=evaluation.get("evaluated_at"),
            condition_met=evaluation.get("condition_met", False),
            current_value=evaluation.get("current_value"),
            threshold=evaluation.get("threshold"),
            details=evaluation.get("details"),
            alert_sent=evaluation.get("alert_sent", False),
            previous_status=evaluation.get("previous_status"),
            new_status=evaluation.get("new_status"),
        ))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_trigger_evaluations(trigger_id: str, limit: int = 50) -> list:
    """Get evaluation history for a trigger."""
    session = _session()
    try:
        rows = session.query(TriggerEvaluation).filter_by(
            trigger_id=trigger_id
        ).order_by(TriggerEvaluation.created_at.desc()).limit(limit).all()
        return [{
            "evaluated_at": r.evaluated_at,
            "condition_met": r.condition_met,
            "current_value": r.current_value,
            "threshold": r.threshold,
            "details": r.details,
            "previous_status": r.previous_status,
            "new_status": r.new_status,
        } for r in rows]
    finally:
        session.close()
