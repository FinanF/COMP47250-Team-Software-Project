"""
optimisation_worker.py
Reads congestion events from event_queue, runs TrafficSignalOptimiser,
sends recommendations to recommendation_queue for the backend to pick up.

Each recommendation includes a unique recommendation_id (UUID).
A 60 second cooldown prevents the same junction from being re-recommended too soon.
pending_changes is handled by Finan after the operator accepts a recommendation.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from optimisation.optimiser import TrafficSignalOptimiser

COOLDOWN_SECONDS = 10


async def optimisation_worker(
    event_queue: asyncio.Queue,
    recommendation_queue: asyncio.Queue,
):
    optimiser = TrafficSignalOptimiser()
    last_recommended = {}

    try:
        from backend.simulation.sumo_worker import get_phase_structure
        sumo_integration = True
        print("[OptimisationWorker] SUMO phase structure available.")
    except ImportError:
        sumo_integration = False
        print("[OptimisationWorker] Running without SUMO integration.")

    print("[OptimisationWorker] Started, waiting for congestion events...")

    while True:
        try:
            event = await event_queue.get()

            pattern  = event.get("pattern_type", "unknown")
            junction = event.get("junction_id", "unknown")
            severity = event.get("severity_score", 0.0)

            print(f"[OptimisationWorker] Received: {pattern} at {junction} (severity {severity})")

            if severity < 0.3:
                print(f"[OptimisationWorker] Severity too low, skipping.")
                event_queue.task_done()
                continue

            now = datetime.now(timezone.utc)
            last_time = last_recommended.get(junction)

            if last_time is not None:
                elapsed = (now - last_time).total_seconds()
                if elapsed < COOLDOWN_SECONDS:
                    print(f"[OptimisationWorker] Cooldown active for {junction} ({int(COOLDOWN_SECONDS - elapsed)}s remaining).")
                    event_queue.task_done()
                    continue

            phase_structure = None
            if sumo_integration:
                try:
                    phase_structure = get_phase_structure(junction)
                except Exception as e:
                    print(f"[OptimisationWorker] Could not get phase structure: {e}")

            recommendation = optimiser.optimise(event, phase_structure=phase_structure)

            if recommendation is None:
                print(f"[OptimisationWorker] No recommendation produced for {junction}.")
                event_queue.task_done()
                continue

            rec_dict = {
                "recommendation_id":   str(uuid.uuid4()),
                "junction_id":         recommendation.junction_id,
                "pattern_type":        recommendation.pattern_type,
                "severity_score":      recommendation.severity_score,
                "old_cycle_length":    recommendation.old_cycle_length,
                "new_cycle_length":    recommendation.new_cycle_length,
                "old_phase_splits":    recommendation.old_phase_splits,
                "new_phase_splits":    recommendation.new_phase_splits,
                "new_phase_durations": recommendation.new_phase_durations,
                "before_max_queue":    recommendation.before_max_queue,
                "after_est_queue":     recommendation.after_est_queue,
                "before_avg_wait":     recommendation.before_avg_wait,
                "after_est_wait":      recommendation.after_est_wait,
                "improvement_pct":     recommendation.improvement_pct,
                "explanation":         recommendation.explanation,
                "created_at":          recommendation.created_at,
            }

            last_recommended[junction] = now
            await recommendation_queue.put(rec_dict)

            print(f"[OptimisationWorker] Recommendation {rec_dict['recommendation_id']} queued for {junction}.")

            event_queue.task_done()

        except asyncio.CancelledError:
            print("[OptimisationWorker] Shutting down.")
            break

        except Exception as e:
            print(f"[OptimisationWorker] Error: {e}")
            event_queue.task_done()
