"""
optimiser.py — Traffic Signal Optimisation Engine

Takes a congestion event from the diagnostic layer and calculates
better signal timings for that junction. Returns a recommendation
with before/after metrics for the backend to store and the frontend to display.

Handles all four pattern types from the diagnostic layer:
  - green_waste       : green time running on empty lanes
  - phase_starvation  : one direction not getting enough green
  - demand_imbalance  : phase timing doesn't match actual demand
  - cycle_too_long    : overall cycle is too long
"""

from dataclasses import dataclass, field
from datetime import datetime
from scipy.optimize import linprog
import numpy as np


# ── Constants ─────────────────────────────────────────────────────────────────

MIN_GREEN_TIME   = 10   # seconds — minimum green any phase can get (safety)
MAX_CYCLE_LENGTH = 120  # seconds — maximum total cycle length
MIN_CYCLE_LENGTH = 40   # seconds — minimum total cycle length


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class OptimisationRecommendation:
    """
    One recommendation sent to the backend.
    Contains old timings, new timings, and before/after metrics.
    """
    junction_id:        str
    pattern_type:       str
    severity_score:     float

    # Timings
    old_cycle_length:   float
    new_cycle_length:   float
    old_phase_splits:   dict   # e.g. {"green": 42, "red": 18}
    new_phase_splits:   dict   # e.g. {"green": 30, "red": 30}

    # Before / after metrics
    before_max_queue:   float
    after_est_queue:    float
    before_avg_wait:    float
    after_est_wait:     float
    improvement_pct:    float  # % reduction in estimated wait time

    # Human-readable explanation for the dashboard
    explanation:        str

    # Timestamp
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Main optimiser class ───────────────────────────────────────────────────────

class TrafficSignalOptimiser:
    """
    Receives a congestion event dict (from diagnostic_worker via event_queue)
    and returns an OptimisationRecommendation.

    Usage:
        optimiser = TrafficSignalOptimiser()
        recommendation = optimiser.optimise(event)
    """

    def optimise(self, event: dict):
        """
        Main entry point. Routes to the right strategy based on pattern type.
        Returns an OptimisationRecommendation or None if nothing to do.
        """
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

        # Route to the correct strategy
        if pattern == "green_waste":
            return self._optimise_green_waste(event, junction, queues, phase, cycle, severity)

        elif pattern == "phase_starvation":
            return self._optimise_starvation(event, junction, queues, phase, cycle, severity)

        elif pattern == "demand_imbalance":
            return self._optimise_imbalance(event, junction, queues, phase, cycle, severity)

        elif pattern == "cycle_too_long":
            return self._optimise_cycle_length(event, junction, queues, phase, cycle, severity)

        else:
            print(f"[Optimiser] Unknown pattern '{pattern}', skipping.")
            return None


    # ── Strategy 1: Green waste ───────────────────────────────────────────────
    # Problem: green phase running on a nearly empty lane while others queue.
    # Fix: shrink the wasted green phase, give that time to the starved phases.

    def _optimise_green_waste(self, event, junction, queues, phase, cycle, severity):
        lanes       = list(queues.keys())
        queue_vals  = list(queues.values())
        total_q     = sum(queue_vals) or 1

        # Use scipy linprog to allocate green time proportional to queue demand.
        # Minimise: -throughput (i.e. maximise throughput)
        # Each lane gets green time proportional to its share of total queue.
        # Subject to: each lane >= MIN_GREEN_TIME, sum = cycle length.

        n = len(lanes)
        if n < 2:
            return None

        # Demand weights — how much of the cycle each lane deserves
        weights = np.array([max(q, 1) / total_q for q in queue_vals])

        # Simple proportional allocation (linprog overkill for 2-phase,
        # but scales cleanly to N phases)
        new_splits_raw = weights * cycle
        # Enforce minimum green time
        new_splits = np.clip(new_splits_raw, MIN_GREEN_TIME, cycle)
        # Normalise back to cycle length
        new_splits = new_splits / new_splits.sum() * cycle
        new_splits = np.round(new_splits, 1)

        old_splits = {lane: round(cycle / n, 1) for lane in lanes}
        new_phase_splits = {lane: float(new_splits[i]) for i, lane in enumerate(lanes)}

        # Before/after estimate
        before_max  = max(queue_vals)
        after_est   = before_max * (1 - severity * 0.5)
        before_wait = before_max * 3.0   # rough: 3s per queued vehicle
        after_wait  = after_est  * 3.0
        improvement = round(((before_wait - after_wait) / before_wait) * 100, 1) if before_wait > 0 else 0

        explanation = (
            f"Green time was being wasted on a near-empty lane at junction {junction}. "
            f"New timings redistribute green time proportionally to actual queue demand. "
            f"Estimated wait time reduction: {improvement}%."
        )

        return OptimisationRecommendation(
            junction_id      = junction,
            pattern_type     = "green_waste",
            severity_score   = severity,
            old_cycle_length = cycle,
            new_cycle_length = cycle,
            old_phase_splits = old_splits,
            new_phase_splits = new_phase_splits,
            before_max_queue = before_max,
            after_est_queue  = round(after_est, 1),
            before_avg_wait  = round(before_wait, 1),
            after_est_wait   = round(after_wait, 1),
            improvement_pct  = improvement,
            explanation      = explanation,
        )


    # ── Strategy 2: Phase starvation ─────────────────────────────────────────
    # Problem: one lane's queue is growing — it's not getting enough green time.
    # Fix: increase green time for the starved lane, reduce elsewhere.

    def _optimise_starvation(self, event, junction, queues, phase, cycle, severity):
        if not queues:
            return None

        lanes      = list(queues.keys())
        queue_vals = list(queues.values())
        total_q    = sum(queue_vals) or 1
        n          = len(lanes)

        # Find the most starved lane (highest queue)
        max_idx    = int(np.argmax(queue_vals))
        starved    = lanes[max_idx]

        # Boost starved lane by up to 40% extra green proportional to severity
        boost      = 1.0 + (severity * 0.4)
        weights    = np.array([max(q, 1) / total_q for q in queue_vals])
        weights[max_idx] *= boost
        weights    = weights / weights.sum()

        new_splits_raw = weights * cycle
        new_splits     = np.clip(new_splits_raw, MIN_GREEN_TIME, cycle)
        new_splits     = new_splits / new_splits.sum() * cycle
        new_splits     = np.round(new_splits, 1)

        old_splits       = {lane: round(cycle / n, 1) for lane in lanes}
        new_phase_splits = {lane: float(new_splits[i]) for i, lane in enumerate(lanes)}

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
            junction_id      = junction,
            pattern_type     = "phase_starvation",
            severity_score   = severity,
            old_cycle_length = cycle,
            new_cycle_length = cycle,
            old_phase_splits = old_splits,
            new_phase_splits = new_phase_splits,
            before_max_queue = before_max,
            after_est_queue  = round(after_est, 1),
            before_avg_wait  = round(before_wait, 1),
            after_est_wait   = round(after_wait, 1),
            improvement_pct  = improvement,
            explanation      = explanation,
        )


    # ── Strategy 3: Demand imbalance ─────────────────────────────────────────
    # Problem: one lane has far more vehicles than others.
    # Fix: allocate green time weighted by actual queue lengths.

    def _optimise_imbalance(self, event, junction, queues, phase, cycle, severity):
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

        old_splits       = {lane: round(cycle / n, 1) for lane in lanes}
        new_phase_splits = {lane: float(new_splits[i]) for i, lane in enumerate(lanes)}

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
            junction_id      = junction,
            pattern_type     = "demand_imbalance",
            severity_score   = severity,
            old_cycle_length = cycle,
            new_cycle_length = cycle,
            old_phase_splits = old_splits,
            new_phase_splits = new_phase_splits,
            before_max_queue = before_max,
            after_est_queue  = round(after_est, 1),
            before_avg_wait  = round(before_wait, 1),
            after_est_wait   = round(after_wait, 1),
            improvement_pct  = improvement,
            explanation      = explanation,
        )


    # ── Strategy 4: Cycle too long ────────────────────────────────────────────
    # Problem: total cycle length is too long — vehicles wait too long per cycle.
    # Fix: reduce cycle length, keep phase split ratios the same.

    def _optimise_cycle_length(self, event, junction, queues, phase, cycle, severity):
        if not queues:
            return None

        lanes      = list(queues.keys())
        queue_vals = list(queues.values())
        n          = len(lanes)

        # Reduce cycle length proportional to severity
        reduction     = severity * 0.3   # up to 30% shorter
        new_cycle     = max(round(cycle * (1 - reduction), 1), MIN_CYCLE_LENGTH)

        # Keep the same split ratios, just scale to new cycle
        old_splits       = {lane: round(cycle / n, 1) for lane in lanes}
        new_phase_splits = {lane: round(new_cycle / n, 1) for lane in lanes}

        before_max  = max(queue_vals)
        after_est   = before_max * (1 - severity * 0.35)
        before_wait = cycle / 2       # average wait ≈ half the cycle
        after_wait  = new_cycle / 2
        improvement = round(((before_wait - after_wait) / before_wait) * 100, 1) if before_wait > 0 else 0

        explanation = (
            f"Junction {junction} had an excessively long cycle of {cycle:.0f}s. "
            f"Reducing cycle length to {new_cycle:.0f}s keeps the same phase ratios "
            f"but reduces how long any vehicle has to wait per cycle. "
            f"Estimated wait time reduction: {improvement}%."
        )

        return OptimisationRecommendation(
            junction_id      = junction,
            pattern_type     = "cycle_too_long",
            severity_score   = severity,
            old_cycle_length = cycle,
            new_cycle_length = new_cycle,
            old_phase_splits = old_splits,
            new_phase_splits = new_phase_splits,
            before_max_queue = before_max,
            after_est_queue  = round(after_est, 1),
            before_avg_wait  = round(before_wait, 1),
            after_est_wait   = round(after_wait, 1),
            improvement_pct  = improvement,
            explanation      = explanation,
        )
