import asyncio
import os
from sumo_worker import sumo_worker

async def stress_test():
    os.environ["DEMAND_PROFILE"] = "peak"
    os.environ["INJECT_CONGESTION"] = "true"

    traffic_queue = asyncio.Queue(maxsize=500)
    db_queue = asyncio.Queue(maxsize=100)
    shutdown_event = asyncio.Event()

    worker_task = asyncio.create_task(
        sumo_worker(traffic_queue, shutdown_event, db_queue=db_queue)
    )

    max_depth_seen = 0
    near_full_count = 0
    frames = 0

    while not shutdown_event.is_set():
        try:
            msg = await asyncio.wait_for(traffic_queue.get(), timeout=2.0)
            depth = traffic_queue.qsize()
            frames += 1

            if depth > max_depth_seen:
                max_depth_seen = depth
            if depth > 400:  # >80% full
                near_full_count += 1
                print(f"[STRESS] Queue depth warning: {depth}/500 at frame {frames}")

            if frames >= 120:  # 2 minutes
                shutdown_event.set()

        except asyncio.TimeoutError:
            if shutdown_event.is_set():
                break

    await worker_task

    print(f"\n[STRESS] Results after {frames}s:")
    print(f"  Max queue depth:      {max_depth_seen}/500")
    print(f"  Near-full incidents:  {near_full_count}")
    print(f"  {'PASS' if near_full_count < 5 else 'FAIL'}")

asyncio.run(stress_test())
