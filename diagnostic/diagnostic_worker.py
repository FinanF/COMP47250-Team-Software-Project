"""
diagnostic_worker.py — asyncio background task
Reads from traffic_queue, runs DiagnosticEngine, emits to event_queue.
Finan launches this from main.py lifespan.
"""

import asyncio
import json
from diagnostic.engine import DiagnosticEngine


async def diagnostic_worker(
    traffic_queue: asyncio.Queue,
    event_queue:   asyncio.Queue,
    ml_model=None
):
    """
    Runs forever as an asyncio background task.
    Picks up traffic states, runs detection, puts events downstream.
    """
    print("[DiagnosticWorker] Starting diagnostic worker...")
    engine = DiagnosticEngine()
    print("[DiagnosticWorker] Started — waiting for traffic states...")

    while True:
        try:
            # Block until a traffic state arrives from Ruhao's SUMO worker
            state = await traffic_queue.get()
            # Run both detection layers
            if state["type"] != "junction_state":
                continue
            all_events=[]
            for junction in state["junctions"]:
                events = engine.analyse(junction)
                all_events.extend(events)
            if len(all_events)>0:
                print(f"[DiagnosticWorker] Detected {len(all_events)} events.")
            # Push each event downstream to Princeton's optimisation worker
            for event in all_events:
                event_dict = {
                    "junction_id":    event.junction_id,
                    "pattern_type":   event.pattern_type,
                    "severity_score": event.severity_score,
                    "explanation":    event.explanation,
                    "queues":         event.queues,
                    "active_phase":   event.active_phase,
                    "detected_at":    event.detected_at,
                }
                await event_queue.put(event_dict)
                print(
                    f"[DiagnosticWorker] Event: {event.pattern_type} "
                    f"at {event.junction_id} (severity {event.severity_score})"
                )

            traffic_queue.task_done()

        except asyncio.CancelledError:
            print("[DiagnosticWorker] Shutting down.")
            break
        except Exception as e:
            print(f"[DiagnosticWorker] Error processing state: {e}")
            traffic_queue.task_done()
