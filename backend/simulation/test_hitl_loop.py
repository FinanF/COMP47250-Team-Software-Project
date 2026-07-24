import asyncio
import httpx
import websockets
import json

BASE_URL = "http://localhost:8000"
OPT_WS_URL = "ws://localhost:8000/opt"
TRAFFIC_WS_URL = "ws://localhost:8000/traffic"

JUNCTION_POLL_ATTEMPTS = 20
JUNCTION_POLL_INTERVAL = 3
MIN_JUNCTIONS = 10
REC_WAIT_TIMEOUT = 120  # seconds to wait for first recommendation


async def test_hitl_loop():
    async with httpx.AsyncClient(timeout=10.0) as client:

        # Step 1: Wait for junctions to be seeded
        print("Step 1: Waiting for junctions to be seeded...")
        junctions = []
        for attempt in range(JUNCTION_POLL_ATTEMPTS):
            try:
                r = await client.get(f"{BASE_URL}/junctions")
                r.raise_for_status()
                data = r.json()
                junctions = data.get("data", []) if isinstance(data, dict) else data
                print(f"Attempt {attempt + 1}: {len(junctions)} junctions")
                if len(junctions) >= MIN_JUNCTIONS:
                    break
            except Exception as e:
                print(f"Attempt {attempt + 1}: {e}")
            await asyncio.sleep(JUNCTION_POLL_INTERVAL)

        assert len(junctions) >= MIN_JUNCTIONS, (
            f"Expected ≥{MIN_JUNCTIONS} junctions, got {len(junctions)}"
        )
        print(f"{len(junctions)} junctions seeded")

        # Step 2: Connect to /opt WebSocket and wait for a recommendation
        print("\nStep 2: Connecting to /opt WebSocket, waiting for recommendation...")
        print(f"(timeout: {REC_WAIT_TIMEOUT}s)")

        async with websockets.connect(OPT_WS_URL) as opt_ws:

            # Wait for first recommendation message
            rec = None
            start = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start < REC_WAIT_TIMEOUT:
                try:
                    raw = await asyncio.wait_for(opt_ws.recv(), timeout=5.0)
                    message = json.loads(raw)

                    if message.get("type") == "recommendation":
                        rec = message["data"]
                        print(f"Recommendation received")
                        print(f"ID:          {rec.get('recommendation_id')}")
                        print(f"Junction:    {rec.get('junction_id')}")
                        print(f"Pattern:     {rec.get('pattern_type')}")
                        print(f"Explanation: {rec.get('explanation')}")
                        print(f"Before queue:{rec.get('before_max_queue')}")
                        print(f"Est. after:  {rec.get('after_est_queue')}")
                        break
                    else:
                        print(f"Received message type: {message.get('type')} — waiting...")

                except asyncio.TimeoutError:
                    elapsed = asyncio.get_event_loop().time() - start
                    print(f"Still waiting... ({elapsed:.0f}s elapsed)")

            assert rec is not None, (
                f"No recommendation received within {REC_WAIT_TIMEOUT}s — "
                f"check diagnostic and optimisation workers"
            )

            rec_id = rec.get("recommendation_id")
            junction_id = rec.get("junction_id")

            # Step 3: Accept the recommendation (the human-in-the-loop action)
            print(f"\nStep 3: Accepting recommendation {rec_id}...")
            await opt_ws.send(json.dumps({
                "action": "accept",
                "recommendation_id": rec_id
            }))
            print("Accept message sent")

            # Step 4: Wait for status confirmation from the simulation
            print("\nStep 4: Waiting for signal change confirmation...")
            confirmed = False

            while asyncio.get_event_loop().time() - start < REC_WAIT_TIMEOUT + 30:
                try:
                    raw = await asyncio.wait_for(opt_ws.recv(), timeout=10.0)
                    message = json.loads(raw)

                    if message.get("type") == "decision_result":
                        result = message["data"]
                        status = result.get("status")
                        print(f"Signal change status: {status}")

                        if status == "applied":
                            print(f"Signal change applied to {junction_id}")
                            confirmed = True
                            break
                        elif status == "queued":
                            print("Change queued — waiting for application...")
                        elif status == "failed":
                            print(f"[WARN] Signal change failed: {result}")
                            break

                except asyncio.TimeoutError:
                    print("Still waiting for confirmation...")

            assert confirmed, (
                f"Signal change for {junction_id} was never confirmed as 'applied' — "
                f"check apply_pending_changes in sumo_worker"
            )

        # Step 5: Wait for post-change measurement, verify audit log
        print(f"\nStep 5: Waiting 45s for post-change measurement...")
        await asyncio.sleep(45)

        print("Checking audit log...")
        r = await client.get(f"{BASE_URL}/logs")
        r.raise_for_status()
        data = r.json()
        logs = data.get("data", [])

        junction_logs = [l for l in logs if l.get("junction_id") == junction_id]

        if junction_logs:
            log = junction_logs[-1]
            print(f"Audit record found")
            print(f"Before avg queue: {log.get('before_avg_queue')}")
            print(f"After avg queue:  {log.get('after_avg_queue')}")
            print(f"Queue reduction:  {log.get('queue_reduction_pct')}%")
            print(f"Wait reduction:   {log.get('wait_reduction_pct')}%")
        else:
            print(f"[WARN] No audit record for {junction_id} yet — "
                  f"post-change measurement may still be pending "
                  f"(fires at step + {120 * 0.5:.0f}s sim time)")

        # Step 6: Confirm simulation still live
        print("\nStep 6: Confirming simulation still live...")
        r = await client.get(f"{BASE_URL}/junctions")
        assert r.status_code == 200
        print("Simulation still responding")

        print("\nHITL LOOP TEST PASSED")
        print(f"Junction tested:   {junction_id}")
        print(f"Recommendation ID: {rec_id}")


if __name__ == "__main__":
    asyncio.run(test_hitl_loop())
