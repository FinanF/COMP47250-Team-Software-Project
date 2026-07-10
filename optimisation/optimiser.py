"""
optimiser.py — Traffic Signal Optimisation Engine

Takes a congestion event from the diagnostic layer and calculates
better signal timings for that junction. Returns a recommendation
with before/after metrics for the backend to store and the frontend to display.

Updated: now outputs new_phase_durations (flat list in phase order)
alongside new_phase_splits (for dashboard), as requested by Ruhao.
"""

from dataclasses import dataclass, field
from datetime import datetime
from scipy.optimize import linprog
import numpy as np


# ── Constants ─────────────────────────────────────────────────────────────────

MIN_GREEN_TIME   = 10   # seconds — minimum green any phase can get (safety)
MAX_CYCLE_LENGTH = 120  # seconds — maximum total cycle length
MIN_CYCLE_LENGTH = 40   # seconds — minimum total cycle length
YELLOW_DURATION  = 3.0  # seconds — yellow phase duration (never changed)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class OptimisationRecommendation:
    """
    One recommendation sent to the backend.
    Contains old timings, new timings, and before/after metrics.
    """
    junction_id:         str
    pattern_type:        str
    severity_score:      float

    # Timings
    old_cycle_length:    float
    new_cycle_length:    float
    old_phase_splits:    dict    # e.g. {"lane_A": 42, "lane_B": 18} — for dashboard
    new_phase_splits:    dict    # e.g. {"lane_A": 30, "lane_B": 30} — for dashboard
    new_phase_durations: list    # e.g. [30.0, 3.0, 30.0, 3.0] — for Ruhao's SUMO apply

    # Before / after metrics
    before_max_queue:    float
    after_est_queue:     float
    before_avg_wait:     float
    after_est_wait:      float
    improvement_pct:     float

    # Human-readable explanation for the dashboard
    explanation:         str

    # Timestamp
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def build_phase_durations(new_splits: dict, phase_structure: list) -> list:
    """
    Converts new_phase_splits into a flat new_phase_durations list
    that matches the full SUMO phase structure (including yellow phases).

    phase_structure comes from Ruhao's get_phase_structure() helper:
    [{"index": 0, "duration": 42.0, "state": "GGrr", "is_green": True}, ...]

    Green phases get the new optimised durations.
    Yellow/all-red phases keep their existing duration unchanged.
    """
    if not phase_structure:
        # Fallback: no phase structure provided, build a simple 4-phase list
        # [green-A, yellow, green-B, yellow] using the split values
        splits = list(new_splits.values())
        if len(splits) >= 2:
            return [splits[0], YELLOW_DURATION, splits[1], YELLOW_DURATION]
        return [splits[0], YELLOW_DURATION] if splits else []

    green_durations = list(new_splits.values())
    green_index = 0
    result = []

    for phase in phase_structure:
        if phase.get("is_green"):
            # Replace with optimised duration
            if green_index < len(green_durations):
                result.append(round(green_durations[green_index], 1))
                green_index += 1
            else:
                result.append(phase["duration"])
        else:
            # Yellow / all-red — never touch these
            result.append(phase["duration"])

    return result


# ── Main optimiser class ───────────────────────────────────────────────────────

class TrafficSignalOptimiser:
    """
    Receives a congestion event dict (from diagnostic_worker via event_queue)
    and returns an OptimisationRecommendation.

    Usage:
        optimiser = TrafficSignalOptimiser()
        recommendation = optimiser.optimise(event, phase_structure=None)

    phase_structure: optional list from Ruhao's get_phase_structure() helper.
    If None, a default 4-phase structure is assumed.
    """

    def optimise(self, event: dict, phase_structure: list = None):
        pattern   = event.get("pattern_type", "")
        severity  = event.get("severity_score", 0.0)
        junction  = event.get("junction_id", "unknown")
        queues    = event.get("queues", {})
        phase     = event.get("active_phase", "0")
        cycle     = float(event.get("phase_duration_total", 60))

        print(f"[Optimiser] Processing {pattern} at {junction} (severity {severity})")

        if not queues:
            print(f"[Optimiser] No queue data for {junction}, skipping.")
            return None

        if pattern == "green_waste":
            return self._optimise_green_waste(event, junction, queues, phase, cycle, severity, phase_structure)
        elif pattern == "phase_starvation":
            return self._optimise_starvation(event, junction, queues, phase, cycle, severity, phase_structure)
        elif pattern == "demand_imbalance":
            return self._optimise_imbalance(event, junction, queues, phase, cycle, severity, phase_structure)
        elif pattern == "cycle_too_long":
            return self._optimise_cycle_length(event, junction, queues, phase, cycle, severity, phase_structure)
        else:
            print(f"[Optimiser] Unknown pattern '{pattern}', skipping.")
            return None


    def _optimise_green_waste(self, event, junction, queues, phase, cycle, severity, phase_structure):
        lanes      = list(queues.keys())
        queue_vals = list(queues.values())
        total_q    = sum(queue_vals) or 1
        n          = len(lanes)
        if n < 2:
            return None

        weights        = np.array([max(q, 1) / total_q for q in queue_vals])
        new_splits_raw = weights * cycle
        new_splits     = np.clip(new_splits_raw, MIN_GREEN_TIME, cycle)
        new_splits     = new_splits / new_splits.sum() * cycle
        new_splits     = np.round(new_splits, 1)

        old_splits       = {lane: round(cycle / n, 1) for lane in lanes}
        new_phase_splits = {lane: float(new_splits[i]) for i, lane in enumerate(lanes)}
        new_phase_durations = build_phase_durations(new_phase_splits, phase_structure)

        before_max  = max(queue_vals)
        after_est   = before_max * (1 - severity * 0.5)
        before_wait = before_max * 3.0
        after_wait  = after_est  * 3.0
        improvement = round(((before_wait - after_wait) / before_wait) * 100, 1) if before_wait > 0 else 0

        explanation = (
            f"Green time was being wasted on a near-empty lane at junction {junction}. "
            f"New timings redistribute green time proportionally to actual queue demand. "
            f"Estimated wait time reduction: {improvement}%."
        )

        return OptimisationRecommendation(
            junction_id=junction, pattern_type="green_waste", severity_score=severity,
            old_cycle_length=cycle, new_cycle_length=cycle,
            old_phase_splits=old_splits, new_phase_splits=new_phase_splits,
            new_phase_durations=new_phase_durations,
            before_max_queue=before_max, after_est_queue=round(after_est, 1),
            before_avg_wait=round(before_wait, 1), after_est_wait=round(after_wait, 1),
            improvement_pct=improvement, explanation=explanation,
        )


    def _optimise_starvation(self, event, junction, queues, phase, cycle, severity, phase_structure):
        if not queues:
            return None
        lanes      = list(queues.keys())
        queue_vals = list(queues.values())
        total_q    = sum(queue_vals) or 1
        n          = len(lanes)
        max_idx    = int(np.argmax(queue_vals))
        starved    = lanes[max_idx]

        boost      = 1.0 + (severity * 0.4)
        weights    = np.array([max(q, 1) / total_q for q in queue_vals])
        weights[max_idx] *= boost
        weights    = weights / weights.sum()

        new_splits_raw = weights * cycle
        new_splits     = np.clip(new_splits_raw, MIN_GREEN_TIME, cycle)
        new_splits     = new_splits / new_splits.sum() * cycle
        new_splits     = np.round(new_splits, 1)

        old_splits          = {lane: round(cycle / n, 1) for lane in lanes}
        new_phase_splits    = {lane: float(new_splits[i]) for i, lane in enumerate(lanes)}
        new_phase_durations = build_phase_durations(new_phase_splits, phase_structure)

        before_max  = max(queue_vals)
        after_est   = before_max * (1 - severity * 0.55)
        before_wait = before_max * 3.5
        after_wait  = after_est  * 3.5
        improvement = round(((before_wait - after_wait) / before_wait) * 100, 1) if before_wait > 0 else 0

        explanation = (
            f"Lane {starved} at junction {junction} was being starved of green time "
            f"while its queue grew to {before_max} vehicles. "
            f"New timings give it {new_phase_splits.get(starved, 0):.1f}s of green "
            f"(was ~{old_splits.get(starved, 0):.1f}s). "
            f"Estimated wait time reduction: {improvement}%."
        )

        return OptimisationRecommendation(
            junction_id=junction, pattern_type="phase_starvation", severity_score=severity,
            old_cycle_length=cycle, new_cycle_length=cycle,
            old_phase_splits=old_splits, new_phase_splits=new_phase_splits,
            new_phase_durations=new_phase_durations,
            before_max_queue=before_max, after_est_queue=round(after_est, 1),
            before_avg_wait=round(before_wait, 1), after_est_wait=round(after_wait, 1),
            improvement_pct=improvement, explanation=explanation,
        )


    def _optimise_imbalance(self, event, junction, queues, phase, cycle, severity, phase_structure):
        if not queues:
            return None
        lanes      = list(queues.keys())
        queue_vals = list(queues.values())
        total_q    = sum(queue_vals) or 1
        n          = len(lanes)

        weights        = np.array([max(q, 1) / total_q for q in queue_vals])
        new_splits_raw = weights * cycle
        new_splits     = np.clip(new_splits_raw, MIN_GREEN_TIME, cycle)
        new_splits     = new_splits / new_splits.sum() * cycle
        new_splits     = np.round(new_splits, 1)

        old_splits          = {lane: round(cycle / n, 1) for lane in lanes}
        new_phase_splits    = {lane: float(new_splits[i]) for i, lane in enumerate(lanes)}
        new_phase_durations = build_phase_durations(new_phase_splits, phase_structure)

        before_max  = max(queue_vals)
        before_avg  = total_q / n
        after_est   = before_max * (1 - severity * 0.45)
        before_wait = before_avg * 4.0
        after_wait  = (after_est / n) * 4.0
        improvement = round(((before_wait - after_wait) / before_wait) * 100, 1) if before_wait > 0 else 0

        explanation = (
            f"Junction {junction} has a demand imbalance — one lane had {before_max} vehicles "
            f"versus an average of {before_avg:.1f}. "
            f"New timings weight green time by actual queue length rather than splitting equally. "
            f"Estimated wait time reduction: {improvement}%."
        )

        return OptimisationRecommendation(
            junction_id=junction, pattern_type="demand_imbalance", severity_score=severity,
            old_cycle_length=cycle, new_cycle_length=cycle,
            old_phase_splits=old_splits, new_phase_splits=new_phase_splits,
            new_phase_durations=new_phase_durations,
            before_max_queue=before_max, after_est_queue=round(after_est, 1),
            before_avg_wait=round(before_wait, 1), after_est_wait=round(after_wait, 1),
            improvement_pct=improvement, explanation=explanation,
        )


    def _optimise_cycle_length(self, event, junction, queues, phase, cycle, severity, phase_structure):
        if not queues:
            return None
        lanes      = list(queues.keys())
        queue_vals = list(queues.values())
        n          = len(lanes)

        reduction        = severity * 0.3
        new_cycle        = max(round(cycle * (1 - reduction), 1), MIN_CYCLE_LENGTH)
        old_splits       = {lane: round(cycle / n, 1) for lane in lanes}
        new_phase_splits = {lane: round(new_cycle / n, 1) for lane in lanes}
        new_phase_durations = build_phase_durations(new_phase_splits, phase_structure)

        before_max  = max(queue_vals)
        after_est   = before_max * (1 - severity * 0.35)
        before_wait = cycle / 2
        after_wait  = new_cycle / 2
        improvement = round(((before_wait - after_wait) / before_wait) * 100, 1) if before_wait > 0 else 0

        explanation = (
            f"Junction {junction} had an excessively long cycle of {cycle:.0f}s. "
            f"Reducing cycle length to {new_cycle:.0f}s keeps the same phase ratios "
            f"but reduces how long any vehicle has to wait per cycle. "
            f"Estimated wait time reduction: {improvement}%."
        )

        return OptimisationRecommendation(
            junction_id=junction, pattern_type="cycle_too_long", severity_score=severity,
            old_cycle_length=cycle, new_cycle_length=new_cycle,
            old_phase_splits=old_splits, new_phase_splits=new_phase_splits,
            new_phase_durations=new_phase_durations,
            before_max_queue=before_max, after_est_queue=round(after_est, 1),
            before_avg_wait=round(before_wait, 1), after_est_wait=round(after_wait, 1),
            improvement_pct=improvement, explanation=explanation,
        )
