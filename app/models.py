from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class Driver:
    name: str
    description: str
    importance: int
    direction: str
    monitoring_required: bool
    source_type: str

# @dataclass
# class Competitor:
#     company: str
#     ticker: str
#     reason: str
#     competitive_overlap: str
#     threat_level: str

@dataclass
class Trigger:
    trigger_id: str
    category: str
    description: str
    confidence: int
    importance: str
    related_driver: str
    related_companies: str
    related_industry: str
    monitoring_frequency: str
    status: str = "Monitoring"
    condition: Optional[Dict[str, Any]] = None
    cooldown_until: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TriggerCondition:
    trigger_id: str
    condition_type: str  # "financial_metric", "news_keyword", "news_sentiment", "news_volume", "price_change"
    metric_name: Optional[str] = None  # e.g., "revenue_growth_ttm", "operating_margin_ttm"
    operator: Optional[str] = None  # "<", ">", "<=", ">=", "==", "!="
    threshold: Optional[float] = None
    unit: Optional[str] = None  # "percent", "ratio", "absolute", "count"
    lookback_periods: int = 1
    period_type: str = "quarterly"  # "quarterly", "annual", "daily"
    consecutive: bool = False
    allow_gaps: bool = True
    keywords: Optional[List[str]] = None  # for news_keyword
    sentiment_threshold: Optional[float] = None  # for news_sentiment, -1 to 1
    volume_multiplier: Optional[float] = None  # for news_volume, e.g., 2.0 = 2x average
    data_source: str = "yahoo_finance_financials"  # "yahoo_finance_financials", "google_news_rss", "yahoo_finance_rss", "yahoo_finance_price"
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggerCondition":
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class MetricHistory:
    id: Optional[int] = None
    company: str = ""
    metric_name: str = ""
    value: float = 0.0
    period_end: str = ""  # ISO format date
    period_type: str = "quarterly"
    source: str = ""
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TriggerEvaluation:
    id: Optional[int] = None
    trigger_id: str = ""
    evaluated_at: str = ""
    condition_met: bool = False
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    details: Optional[str] = None
    alert_sent: bool = False
    previous_status: str = ""
    new_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThesisPoint:
    factor: str
    explanation: str
    evidence: str
    additional_evidence: str = ""
    importance: str = "Medium"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        parts = [f"**{self.factor}**", self.explanation, f"*Evidence: {self.evidence}*"]
        if self.additional_evidence:
            parts.append(f"*Additional: {self.additional_evidence}*")
        return "\n\n".join(parts)


@dataclass
class Thesis:
    company: str
    industry: str
    bull_case: List[ThesisPoint]
    bear_case: List[ThesisPoint]
    base_case: str
    confidence: int
    assumptions: List[str]
    challenge: str
    drivers: List[Driver]
    competitors: List[str]
    # competitors: List[Competitor]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["drivers"] = [asdict(driver) for driver in self.drivers]
        data["bull_case"] = [point.to_dict() for point in self.bull_case]
        data["bear_case"] = [point.to_dict() for point in self.bear_case]
        return data
