"""Pure HOS engine: `plan(TripInput) -> PlanResult`. No Django, no I/O, no clock."""

from .day_splitter import split_days
from .models import (
    DaySheet,
    DutyEvent,
    EngineWarning,
    HosEngineError,
    HosInputError,
    Kind,
    Leg,
    PlanResult,
    Recap,
    Remark,
    Segment,
    Status,
    Summary,
    TripInput,
)
from .simulator import simulate
from .summary import build_summary

__all__ = [
    "DaySheet",
    "DutyEvent",
    "EngineWarning",
    "HosEngineError",
    "HosInputError",
    "Kind",
    "Leg",
    "PlanResult",
    "Recap",
    "Remark",
    "Segment",
    "Status",
    "Summary",
    "TripInput",
    "plan",
]


def plan(inp: TripInput) -> PlanResult:
    """Simulate the trip, split it into day sheets and summarize it."""
    result = simulate(inp)
    sheets = split_days(result.events, result.spans, inp.cycle_used_min)
    summary = build_summary(result.events, result.spans, inp.cycle_used_min, len(sheets))
    return PlanResult(result.events, sheets, summary, result.warnings)
