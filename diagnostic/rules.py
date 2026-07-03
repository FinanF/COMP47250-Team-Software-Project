"""
rules.py — Rule-based congestion pattern detector
Layer 1 of the DiagnosticEngine.

Detects three patterns:
  1. green_waste    — green phase active but that direction has near-zero queue
  2. phase_starvation — one direction's queue keeps growing across multiple readings
  3. demand_imbalance — two directions have very unequal queues but equal phase time
"""

from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime


# ── Thresholds (tweak these once you have real SUMO data) ──────────────────────
GREEN_WASTE_QUEUE_THRESHOLD = 2        # vehicles — below this = effectively empty
STARVATION_GROWTH_STEPS     = 3        # how many consecutive steps queue must grow
STARVATION_MIN_QUEUE        = 5        # minimum queue size to flag starvation
IMBALANCE_RATIO             = 3.0      # flagged direction is 3x the other
IMBALANCE_MIN_QUEUE         = 4        # ignore tiny queues for imbalance check


@dataclass
class CongestionEvent:
    junction_id:   str
    pattern_type:  str          # green_waste | phase_starvation | demand_imbalance
    severity_score: float       # 0.0 → 1.0
    explanation:   str          # plain English for the dashboard
    queues:        dict         # snapshot of queue lengths when detected
    active_phase:  str
    detected_at:   str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RuleBasedDetector:
    """
    Stateful detector — call analyse() on every incoming traffic_state dict.
    Maintains a short history per junction for starvation detection.
    """

    def __init__(self):
        # Store last N queue readings per junction per direction
        self._history: dict[str, dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=STARVATION_GROWTH_STEPS + 1))
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyse(self, state: dict) -> list[CongestionEvent]:
        """
        Takes one traffic_state dict, returns a list of CongestionEvents (may be empty).

        Expected state format:
        {
            "junction_id":             "J_004",
            "timestamp":               "2026-06-17T10:00:00",
            "queues":                  {"north": 18, "south": 0, "east": 2, "west": 14},
            "active_phase":            "north_south",
            "phase_duration_elapsed":  22,
            "phase_duration_total":    30
        }
        """
        events = []
        jid    = state["junction_id"]
        queues = state["queues"]
        phase  = state["active_phase"]

        # Update history
        for direction, length in queues.items():
            self._history[jid][direction].append(length)

        events += self._check_green_waste(jid, queues, phase)
        events += self._check_starvation(jid, queues, phase)
        events += self._check_demand_imbalance(jid, queues, phase)

        return events

    # ── Pattern checks ─────────────────────────────────────────────────────────

    def _check_green_waste(self, jid, queues, phase) -> list[CongestionEvent]:
        """
        Green phase waste: the active phase direction has near-zero queue
        while at least one other direction has a significant queue.
        """
        events = []

        # Figure out which directions are currently getting green
        green_dirs = self._phase_to_directions(phase)
        waiting_dirs = {d: q for d, q in queues.items() if d not in green_dirs}

        for gdir in green_dirs:
            green_queue   = queues.get(gdir, 0)
            max_waiting_q = max(waiting_dirs.values(), default=0)

            if green_queue <= GREEN_WASTE_QUEUE_THRESHOLD and max_waiting_q >= STARVATION_MIN_QUEUE:
                # Severity: how full the waiting directions are relative to max possible
                green_emptiness = 1.0 - (green_queue / max(GREEN_WASTE_QUEUE_THRESHOLD, 1))
                waiting_fullness = min(max_waiting_q / 30.0, 1.0)
                severity = round((green_emptiness + waiting_fullness) / 2, 2)

                worst_dir = max(waiting_dirs, key=waiting_dirs.get)
                explanation = (
                    f"Green phase active for {gdir} direction with only {green_queue} vehicle(s) queued, "
                    f"while {worst_dir} direction has {max_waiting_q} vehicle(s) waiting. "
                    f"Signal time is being wasted on a near-empty approach."
                )

                events.append(CongestionEvent(
                    junction_id    = jid,
                    pattern_type   = "green_waste",
                    severity_score = round(severity, 2),
                    explanation    = explanation,
                    queues         = queues,
                    active_phase   = phase,
                ))

        return events

    def _check_starvation(self, jid, queues, phase) -> list[CongestionEvent]:
        """
        Phase starvation: a direction's queue has grown consistently
        across the last N readings without being cleared.
        """
        events = []
        green_dirs = self._phase_to_directions(phase)

        for direction, history in self._history[jid].items():
            if direction in green_dirs:
                continue  # currently getting green, not starved right now
            if len(history) < STARVATION_GROWTH_STEPS:
                continue  # not enough history yet

            recent = list(history)[-STARVATION_GROWTH_STEPS:]
            is_growing = all(recent[i] < recent[i + 1] for i in range(len(recent) - 1))
            current_q  = queues.get(direction, 0)

            if is_growing and current_q >= STARVATION_MIN_QUEUE:
                growth     = recent[-1] - recent[0]
                severity   = min(current_q / 30.0, 1.0)
                explanation = (
                    f"{direction.capitalize()} direction queue has grown by {growth} vehicle(s) "
                    f"over the last {STARVATION_GROWTH_STEPS} readings, now at {current_q} vehicle(s). "
                    f"This direction is not receiving sufficient green time to clear its queue."
                )

                events.append(CongestionEvent(
                    junction_id    = jid,
                    pattern_type   = "phase_starvation",
                    severity_score = round(severity, 2),
                    explanation    = explanation,
                    queues         = queues,
                    active_phase   = phase,
                ))

        return events

    def _check_demand_imbalance(self, jid, queues, phase) -> list[CongestionEvent]:
        """
        Demand imbalance: two directions on the same phase axis have
        very different queue lengths, suggesting the phase split is wrong.
        """
        events = []

        # Compare opposing direction pairs
        pairs = [("north", "south"), ("east", "west")]
        for d1, d2 in pairs:
            q1 = queues.get(d1, 0)
            q2 = queues.get(d2, 0)

            if max(q1, q2) < IMBALANCE_MIN_QUEUE:
                continue

            ratio = max(q1, q2) / max(min(q1, q2), 1)

            if ratio >= IMBALANCE_RATIO:
                heavy = d1 if q1 > q2 else d2
                light = d2 if q1 > q2 else d1
                heavy_q, light_q = max(q1, q2), min(q1, q2)
                severity = min((ratio - 1) / 9.0, 1.0)  # ratio of 10 = severity 1.0

                explanation = (
                    f"{heavy.capitalize()} direction has {heavy_q} vehicle(s) queued "
                    f"versus only {light_q} on the {light} approach — a {ratio:.1f}x imbalance. "
                    f"Phase timing does not reflect the actual demand distribution."
                )

                events.append(CongestionEvent(
                    junction_id    = jid,
                    pattern_type   = "demand_imbalance",
                    severity_score = round(severity, 2),
                    explanation    = explanation,
                    queues         = queues,
                    active_phase   = phase,
                ))

        return events

    # ── Helper ─────────────────────────────────────────────────────────────────

    def _phase_to_directions(self, phase: str) -> list[str]:
        """
        Maps a phase name to the directions currently getting green.
        Adjust this mapping to match whatever SUMO/Ruhao uses.
        """
        mapping = {
            "north_south": ["north", "south"],
            "east_west":   ["east",  "west"],
            "north":       ["north"],
            "south":       ["south"],
            "east":        ["east"],
            "west":        ["west"],
        }
        return mapping.get(phase, [])
