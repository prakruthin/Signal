from dataclasses import dataclass, asdict
from typing import List, Dict, Any


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Thesis:
    company: str
    industry: str
    bull_case: List[str]
    bear_case: List[str]
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
        return data
