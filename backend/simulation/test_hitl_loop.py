import asyncio
import httpx
import websockets
import json

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/traffic"

async def test_hitl_loop():
    async with httpx.AsyncClient() as client:

        # Step 1: confirm junctions are seeded
        r = await client.get(f"{BASE_URL}/junctions")
        junctions = r.json()
        assert len(junctions) >= 10, f"Expected ≥10 junctions, got {len(junctions)}"
        print(f"  {len(junctions)} junctions seeded")

        # Step 2: wait for a recommendation to appear
        print("Waiting for recommendation...")
        r = await client.get(f"{BASE_URL}/recommendations")
        recs = r.json()
        # Poll until one appears
        for _ in range(30):
            r = await client.get(f"{BASE_URL}/recommendations")
            recs = r.json()
            if recs:
                break
            await asyncio.sleep(2)

        assert recs, "No recommendations appeared after 60s"
        rec = recs[0]
        print(f"  Recommendation received: {rec['pattern_type']} at {rec['junction_id']}")
        print(f"  Before queue: {rec['before_max_queue']} | Estimated after: {rec['after_est_queue']}")

        # Step 3: accept the recommendation
        r = await client.post(
            f"{BASE_URL}/decisions/{rec['id']}",
            json={"action": "accept"}
        )
        assert r.status_code == 200, f"Decision failed: {r.text}"
        print(f"  Accepted recommendation {rec['id']}")

        # Step 4: wait a few simulation cycles and check queue has dropped
        print("Waiting for simulation to reflect change (15s)...")
        await asyncio.sleep(15)

        # Check baseline_snapshots was populated
        from backend.simulation.sumo_worker import baseline_snapshots
        junction_id = rec["junction_id"]
        assert junction_id in baseline_snapshots, \
            f"No baseline captured for {junction_id} — change may not have applied"

        snapshot = baseline_snapshots[junction_id]
        print(f"  Baseline captured at sim time {snapshot['captured_at_sim_time']}s")
        print(f"  avg_queue before: {snapshot['avg_queue_length']}")
        print(f"  avg_wait before:  {snapshot['avg_waiting_time']}s")
        print("\nHTIL loop test passed.")

asyncio.run(test_hitl_loop())
