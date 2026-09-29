"""70 hr / 8 day recap block (HOS_ENGINE_SPEC section 6)."""

from bisect import bisect_right

from .models import DutyEvent, Kind, Recap, Status
from .rules import CYCLE_LIMIT_MIN, DAY_MIN, RESTART_MIN


class CycleTimeline:
    """Cycle counter after each event, built once so any minute is answered in O(log n)."""

    def __init__(self, events: tuple[DutyEvent, ...], cycle_used_min: int) -> None:
        self.events = events
        self.starts = [e.start_min_abs for e in events]
        self.ends = [e.end_min_abs for e in events]
        self.after = self._cycle_after_each(events, cycle_used_min)

    @staticmethod
    def _cycle_after_each(events: tuple[DutyEvent, ...], cycle_used_min: int) -> list[int]:
        after, cycle, off_run = [cycle_used_min], cycle_used_min, 0
        for event in events:
            length = event.end_min_abs - event.start_min_abs
            if event.status in (Status.D, Status.ON):
                cycle, off_run = cycle + length, 0
            else:
                off_run += length
                cycle = 0 if off_run >= RESTART_MIN else cycle
            after.append(cycle)
        return after

    def _running(self, minute: int) -> int:
        """Index of the first event still running or not yet started at `minute`."""
        return bisect_right(self.ends, minute)

    def at(self, minute: int) -> int:
        """Cycle after events ended by `minute`, plus the elapsed part of a running on-duty event."""
        index = self._running(minute)
        cycle = self.after[index]
        if index < len(self.events) and self.events[index].status in (Status.D, Status.ON):
            cycle += max(0, minute - self.starts[index])
        return cycle

    def restart_in_progress(self, minute: int) -> bool:
        index = self._running(minute)
        return index < len(self.events) and (
            self.events[index].kind == Kind.RESTART and self.starts[index] < minute
        )


def cycle_at(events: tuple[DutyEvent, ...], cycle_used_min: int, minute: int) -> int:
    return CycleTimeline(events, cycle_used_min).at(minute)


def build_recap(timeline: CycleTimeline, day_index: int, totals: dict[Status, int]) -> Recap:
    midnight = DAY_MIN * (day_index + 1)
    used = timeline.at(midnight)
    noted = timeline.restart_in_progress(midnight)
    return Recap(
        on_duty_today=totals[Status.D] + totals[Status.ON],
        a_last_7=used,
        b_available_tomorrow=CYCLE_LIMIT_MIN if noted else max(0, CYCLE_LIMIT_MIN - used),
        c_last_8=used,
        restart_note=noted,
    )
