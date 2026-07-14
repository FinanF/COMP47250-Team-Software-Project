import asyncio
import csv
import json
import os
from sumo_worker import sumo_worker, INJECT_CONGESTION

# Which junctions get which labels — must match inject_misconfigured_signals()
# tls_ids[0] → starvation, tls_ids[1] → green_waste, tls_ids[2] → demand_imbalance
# All others → normal
INJECTED_PATTERN_INDICES = {
    0: "starvation",
    1: "green_waste",
    2: "demand_imbalance"
}

async def collect_ground_truth(output_csv: str, max_frames: int = 200):
    traffic_queue = asyncio.Queue(maxsize=500)
    db_queue = asyncio.Queue(maxsize=100)
    shutdown_event = asyncio.Event()

    # We need the tls_ids to know which index maps to which label.
    # Temporarily capture them from the first junction_state frame.
    tls_id_order = []
    rows = []

    worker_task = asyncio.create_task(
        sumo_worker(traffic_queue, shutdown_event, db_queue=db_queue)
    )

    frames = 0
    while not shutdown_event.is_set() or not traffic_queue.empty():
        try:
            message = await asyncio.wait_for(traffic_queue.get(), timeout=5.0)

            if message["type"] != "junction_state":
                continue

            # On first frame, record junction order
            if not tls_id_order:
                tls_id_order = [j["id"] for j in message["junctions"]]
                print(f"[GT] Junction order captured: {tls_id_order[:5]}...")

            # Build labelled rows
            for junction in message["junctions"]:
                jid = junction["id"]
                try:
                    idx = tls_id_order.index(jid)
                except ValueError:
                    idx = -1
                label = INJECTED_PATTERN_INDICES.get(idx, "normal")

                # Flatten approaches into aggregate features Aadithya can use
                approaches = junction.get("approaches", [])
                max_queue = max((a["queue_length"] for a in approaches), default=0)
                avg_queue = (
                    sum(a["queue_length"] for a in approaches) / len(approaches)
                    if approaches else 0
                )
                max_wait = max((a["waiting_time_avg"] for a in approaches), default=0)
                green_lanes = sum(1 for a in approaches if a["green"])
                empty_green = sum(
                    1 for a in approaches
                    if a["green"] and a["queue_length"] == 0
                )
                max_since_green = max(
                    (a["seconds_since_green"] for a in approaches
                     if a["seconds_since_green"] is not None),
                    default=None
                )

                rows.append({
                    "sim_time": message["timestamp"],
                    "junction_id": jid,
                    "current_phase": junction["current_phase"],
                    "phase_duration_total": junction["phase_duration_total"],
                    "phase_duration_remaining": junction["phase_duration_remaining"],
                    "max_queue_length": max_queue,
                    "avg_queue_length": round(avg_queue, 2),
                    "max_waiting_time": max_wait,
                    "green_lane_count": green_lanes,
                    "empty_green_lane_count": empty_green,
                    "max_seconds_since_green": max_since_green,
                    "approach_count": len(approaches),
                    "label": label
                })

            frames += 1
            if frames >= max_frames:
                shutdown_event.set()
                break

        except asyncio.TimeoutError:
            if shutdown_event.is_set():
                break

    await worker_task

    # Write CSV
    if rows:
        fieldnames = list(rows[0].keys())
        with open(output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[GT] Written {len(rows)} rows to {output_csv}")
    else:
        print("[GT] No rows collected — check simulation ran correctly")


if __name__ == "__main__":
    os.environ["INJECT_CONGESTION"] = "true"
    asyncio.run(collect_ground_truth("ground_truth.csv", max_frames=50))

