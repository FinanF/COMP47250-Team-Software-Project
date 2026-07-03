"""
rules.py — Rule-based congestion pattern detector
Updated to match Ruhao's actual SUMO junction_state schema.

Detects four patterns:
  1. green_waste       — green lane active but queue_length is zero
  2. phase_starvation  — a non-green lane queue keeps growing
  3. demand_imbalance  — large difference between max and avg queue
  4. cycle_too_long    — total cycle duration excessively long
"""

from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime

# ── Thresholds ────────────────────────────────────────────────────────────────
GREEN_WASTE_WAITING_THRESHOLD = 3
STARVATION_GROWTH_STEPS       = 3
STARVATION_MIN_QUEUE          = 5
IMBALANCE_RATIO               = 3.0
IMBALANCE_MIN_QUEUE           = 4
CYCLE_TOO_LONG_THRESHOLD      = 120


@dataclass
class CongestionEvent:
    junction_id:    str
    pattern_type:   str
    severity_score: float
    explanation:    str
    queues:         dict
    active_phase:   str
    detected_at:    str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RuleBasedDetector:
    def __init__(self):
        self._history: dict[str, dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=STARVATION_GROWTH_STEPS + 1))
        )

    def analyse(self, state: dict) -> list[CongestionEvent]:
        if state.get("type") != "junction_state":
            return []

        events     = []
        jid        = state.get("id", "unknown")
        approaches = state.get("approaches", [])
        phase      = str(state.get("current_phase", 0))
        total      = state.get("phase_duration_total", 0)

        for approach in approaches:
            lane_id = approach.get("lane_id", "unknown")
            q       = approach.get("queue_length", 0)
            self._history[jid][lane_id].append(q)

        queues_snapshot = {
            a.get("lane_id", "unknown"): a.get("queue_length", 0)
            for a in approaches
        }

        events += self._check_green_waste(jid, approaches, phase, queues_snapshot)
        events += self._check_starvation(jid, approaches, phase, queues_snapshot)
        events += self._check_demand_imbalance(jid, approaches, phase, queues_snapshot)
        events += self._check_cycle_too_long(jid, approaches, phase, total, queues_snapshot)
        return events

    def _check_green_waste(self, jid, approaches, phase, queues_snapshot):
        events        = []
        green_lanes   = [a for a in approaches if a.get("green") is True]
        waiting_lanes = [a for a in approaches if a.get("green") is False]
        max_waiting_q = max((a.get("queue_length", 0) for a in waiting_lanes), default=0)

        for lane in green_lanes:
            green_q = lane.get("queue_length", 0)
            lane_id = lane.get("lane_id", "unknown")
            if green_q <= GREEN_WASTE_WAITING_THRESHOLD and max_waiting_q >= STARVATION_MIN_QUEUE:
                green_emptiness  = 1.0 - (green_q / max(GREEN_WASTE_WAITING_THRESHOLD, 1))
                waiting_fullness = min(max_waiting_q / 30.0, 1.0)
                severity         = round((green_emptiness + waiting_fullness) / 2, 2)
                worst_lane       = max(waiting_lanes, key=lambda a: a.get("queue_length", 0))
                explanation = (
                    f"Lane {lane_id} is green with only {green_q} vehicle(s) queued, "
                    f"while lane {worst_lane.get('lane_id')} has {max_waiting_q} vehicle(s) waiting on red. "
                    f"Signal time is being wasted on a near-empty approach."
                )
                events.append(CongestionEvent(jid, "green_waste", severity, explanation, queues_snapshot, phase))
        return events

    def _check_starvation(self, jid, approaches, phase, queues_snapshot):
        events        = []
        waiting_lanes = [a for a in approaches if a.get("green") is False]

        for lane in waiting_lanes:
            lane_id = lane.get("lane_id", "unknown")
            history = self._history[jid][lane_id]
            if len(history) < STARVATION_GROWTH_STEPS:
                continue
            recent     = list(history)[-STARVATION_GROWTH_STEPS:]
            is_growing = all(recent[i] < recent[i + 1] for i in range(len(recent) - 1))
            current_q  = lane.get("queue_length", 0)
            if is_growing and current_q >= STARVATION_MIN_QUEUE:
                growth  = recent[-1] - recent[0]
                ssg     = lane.get("seconds_since_green", 0)
                severity = min(current_q / 30.0, 1.0)
                explanation = (
                    f"Lane {lane_id} queue has grown by {growth} vehicle(s) "
                    f"over the last {STARVATION_GROWTH_STEPS} readings, now at {current_q} vehicle(s). "
                    f"This lane has been waiting {ssg:.0f}s since last green."
                )
                events.append(CongestionEvent(jid, "phase_starvation", round(severity, 2), explanation, queues_snapshot, phase))
        return events

    def _check_demand_imbalance(self, jid, approaches, phase, queues_snapshot):
        events = []
        if len(approaches) < 2:
            return events
        queue_lengths = [a.get("queue_length", 0) for a in approaches]
        max_q  = max(queue_lengths)
        avg_q  = sum(queue_lengths) / len(queue_lengths)
        if max_q < IMBALANCE_MIN_QUEUE:
            return events
        ratio = max_q / max(avg_q, 1)
        if ratio >= IMBALANCE_RATIO:
            severity   = min((ratio - 1) / 9.0, 1.0)
            worst_lane = max(approaches, key=lambda a: a.get("queue_length", 0))
            explanation = (
                f"Junction {jid} has a demand imbalance — lane {worst_lane.get('lane_id')} "
                f"has {max_q} vehicle(s) versus an average of {avg_q:.1f} across all approaches "
                f"({ratio:.1f}x imbalance). Phase timing does not reflect actual demand."
            )
            events.append(CongestionEvent(jid, "demand_imbalance", round(severity, 2), explanation, queues_snapshot, phase))
        return events

    def _check_cycle_too_long(self, jid, approaches, phase, phase_total, queues_snapshot):
        events  = []
        total_q = sum(a.get("queue_length", 0) for a in approaches)
        if phase_total > CYCLE_TOO_LONG_THRESHOLD and total_q > 3:
            severity = min((phase_total - CYCLE_TOO_LONG_THRESHOLD) / 60.0, 1.0)
            explanation = (
                f"Junction {jid} has a total cycle duration of {phase_total:.0f}s — "
                f"vehicles are waiting through excessively long cycles with {total_q} vehicles queued. "
                f"Reducing cycle length would improve throughput."
            )
            events.append(CongestionEvent(jid, "cycle_too_long", round(severity, 2), explanation, queues_snapshot, phase))
        return events
