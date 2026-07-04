"""

optimisation_worker.py — asyncio background task
Reads congestion events from event_queue (put there by diagnostic_worker),
runs TrafficSignalOptimiser, sends recommendations to recommendation_queue
for the backend to pick up.

"""

import asyncio
from optimiser import TrafficSignalOptimiser


async def optimisation_worker(
    event_queue:          asyncio.Queue,
    recommendation_queue: asyncio.Queue,
):
    """
    Runs forever as an asyncio background task.
    Picks up congestion events, runs optimiser, puts recommendations downstream.
    """
    optimiser = TrafficSignalOptimiser()
    print("[OptimisationWorker] Started — waiting for congestion events...")

    while True:
        try:
            # Block until a congestion event arrives from diagnostic_worker
            event = await event_queue.get()

            pattern  = event.get("pattern_type", "unknown")
            junction = event.get("junction_id", "unknown")
            severity = event.get("severity_score", 0.0)

            print(
                f"[OptimisationWorker] Received event: {pattern} "
                f"at {junction} (severity {severity})"
            )

            # Only optimise if severity is high enough to be worth acting on
            if severity < 0.3:
                print(f"[OptimisationWorker] Severity {severity} too low, skipping.")
                event_queue.task_done()
                continue

            # Run the optimiser
            recommendation = optimiser.optimise(event)

            if recommendation is None:
                print(f"[OptimisationWorker] No recommendation produced for {junction}.")
                event_queue.task_done()
                continue

            # Convert to dict for the backend
            rec_dict = {
                "junction_id":       recommendation.junction_id,
                "pattern_type":      recommendation.pattern_type,
                "severity_score":    recommendation.severity_score,
                "old_cycle_length":  recommendation.old_cycle_length,
                "new_cycle_length":  recommendation.new_cycle_length,
                "old_phase_splits":  recommendation.old_phase_splits,
                "new_phase_splits":  recommendation.new_phase_splits,
                "before_max_queue":  recommendation.before_max_queue,
                "after_est_queue":   recommendation.after_est_queue,
                "before_avg_wait":   recommendation.before_avg_wait,
                "after_est_wait":    recommendation.after_est_wait,
                "improvement_pct":   recommendation.improvement_pct,
                "explanation":       recommendation.explanation,
                "created_at":        recommendation.created_at,
            }

            # Push to backend queue
            await recommendation_queue.put(rec_dict)

            print(
                f"[OptimisationWorker] Recommendation sent for {junction}: "
                f"{recommendation.improvement_pct}% estimated improvement."
            )

            event_queue.task_done()

        except asyncio.CancelledError:
            print("[OptimisationWorker] Shutting down.")
            break

        except Exception as e:
            print(f"[OptimisationWorker] Error processing event: {e}")
            event_queue.task_done()
