"""

optimisation_worker.py — asyncio background task
Reads congestion events from event_queue (put there by diagnostic_worker),
runs TrafficSignalOptimiser, sends recommendations to recommendation_queue
for the backend to pick up.

<<<<<<< HEAD
=======
Updated to use Ruhao's build_signal_program() and pending_changes
so all TraCI logic stays in sumo_worker.py.
>>>>>>> 832900036c5a5187f298593b14255cda3ad3c4bc
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

    # Import Ruhao's helpers for applying timings back into SUMO
    try:
        from backend.simulation.sumo_worker import build_signal_program, pending_changes, get_phase_structure
        sumo_integration = True
        print("[OptimisationWorker] SUMO integration enabled via build_signal_program.")
    except ImportError:
        sumo_integration = False
        print("[OptimisationWorker] Running without SUMO integration (build_signal_program not available yet).")

    print("[OptimisationWorker] Started — waiting for congestion events...")

    while True:
        try:
            # Block until a congestion event arrives from diagnostic_worker
            event = await event_queue.get()

            pattern  = event.get("pattern_type", "unknown")
            junction = event.get("junction_id", "unknown")
            severity = event.get("severity_score", 0.0)

            print(
                f"[OptimisationWorker] Received: {pattern} "
                f"at {junction} (severity {severity})"
            )

            # Only optimise if severity is high enough
            if severity < 0.3:
                print(f"[OptimisationWorker] Severity {severity} too low, skipping.")
                event_queue.task_done()
                continue

            # Get phase structure from Ruhao's helper if available
            phase_structure = None
            if sumo_integration:
                try:
                    phase_structure = get_phase_structure(junction)
                    print(f"[OptimisationWorker] Got phase structure for {junction}: {len(phase_structure)} phases.")
                except Exception as e:
                    print(f"[OptimisationWorker] Could not get phase structure for {junction}: {e}")

            # Run the optimiser
            recommendation = optimiser.optimise(event, phase_structure=phase_structure)

            if recommendation is None:
                print(f"[OptimisationWorker] No recommendation produced for {junction}.")
                event_queue.task_done()
                continue

            # Apply into SUMO via Ruhao's build_signal_program helper
            if sumo_integration and recommendation.new_phase_durations:
                try:
                    new_program = build_signal_program(
                        recommendation.junction_id,
                        recommendation.new_phase_durations
                    )
                    pending_changes[recommendation.junction_id] = new_program
                    print(
                        f"[OptimisationWorker] Applied to SUMO pending_changes: "
                        f"{junction} → {recommendation.new_phase_durations}"
                    )
                except Exception as e:
                    print(f"[OptimisationWorker] Could not apply to SUMO: {e}")

            # Build dict for backend / frontend
            rec_dict = {
                "junction_id":        recommendation.junction_id,
                "pattern_type":       recommendation.pattern_type,
                "severity_score":     recommendation.severity_score,
                "old_cycle_length":   recommendation.old_cycle_length,
                "new_cycle_length":   recommendation.new_cycle_length,
                "old_phase_splits":   recommendation.old_phase_splits,
                "new_phase_splits":   recommendation.new_phase_splits,
                "new_phase_durations":recommendation.new_phase_durations,  # for Ruhao's SUMO apply
                "before_max_queue":   recommendation.before_max_queue,
                "after_est_queue":    recommendation.after_est_queue,
                "before_avg_wait":    recommendation.before_avg_wait,
                "after_est_wait":     recommendation.after_est_wait,
                "improvement_pct":    recommendation.improvement_pct,
                "explanation":        recommendation.explanation,
                "created_at":         recommendation.created_at,
            }

            await recommendation_queue.put(rec_dict)

            print(
                f"[OptimisationWorker] Recommendation queued for {junction}: "
                f"{recommendation.improvement_pct}% estimated improvement. "
                f"Phase durations: {recommendation.new_phase_durations}"
            )

            event_queue.task_done()

        except asyncio.CancelledError:
            print("[OptimisationWorker] Shutting down.")
            break

        except Exception as e:
            print(f"[OptimisationWorker] Error: {e}")
            event_queue.task_done()
