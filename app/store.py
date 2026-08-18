import json
import os
from datetime import datetime
from sqlalchemy import create_engine, String, Text, DateTime, Integer
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


class EventLog(Base):
    __tablename__ = "event_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(180), index=True)
    event_text: Mapped[str] = mapped_column(Text)
    evaluation: Mapped[str] = mapped_column(Text)
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


def _session():
    url = os.getenv("DATABASE_URL", "sqlite:///investment_intelligence.db")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def save_thesis(company: str, summary: str, reason: str = "Initial analyst thesis") -> int:
    session = _session()
    latest = session.query(ThesisVersion).filter_by(company=company).order_by(ThesisVersion.version.desc()).first()
    item = ThesisVersion(company=company, version=(latest.version + 1 if latest else 1), summary=summary, reason=reason)
    session.add(item); session.commit(); session.refresh(item); session.close()
    return item.version


def thesis_history(company: str):
    session = _session()
    rows = session.query(ThesisVersion).filter_by(company=company).order_by(ThesisVersion.version.desc()).all()
    result = [[f"v{x.version}", x.reason, x.created_at.strftime("%Y-%m-%d %H:%M"), x.summary[:180] + "…"] for x in rows]
    session.close(); return result


def log_event(company: str, event: str, evaluation: dict):
    session = _session(); session.add(EventLog(company=company, event_text=event, evaluation=json.dumps(evaluation))); session.commit(); session.close()


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
    session = _session()
    row = session.query(TriggerState).filter_by(company=company, trigger_id=trigger_id).first()
    status = row.status if row else None
    session.close()
    return status


def set_trigger_status(company: str, trigger_id: str, status: str):
    session = _session()
    row = session.query(TriggerState).filter_by(company=company, trigger_id=trigger_id).first()
    if row:
        row.status = status
    else:
        session.add(TriggerState(company=company, trigger_id=trigger_id, status=status))
    session.commit(); session.close()
