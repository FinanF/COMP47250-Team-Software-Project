import asyncio
import websockets
import json


async def traffic():
    traffic_light_uri = "ws://127.0.0.1:8000/traffic-lights"
    async with websockets.connect(traffic_light_uri) as ws:
        print("✓ Connected to WebSocket")
        message_count = 0
        try:
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                message_count += 1
                print(data)
                # Print key info from each message
                print(f"\n📨 Message(Junction) #{message_count}")
                print(f"   Timestamp: {data.get('timestamp')}s")
                print(f"   Junctions: {data.get('junction_count')}")
                print(f"   Status: {data.get('sim_status')}")

                # Access junction data
                junctions = data.get('junctions', [])
                if junctions:
                    first_junction = junctions[0]
                    print(f"   First junction: {first_junction['id']}")
                    print(f"   Approaches: {len(first_junction['approaches'])}")
        except KeyboardInterrupt:
            print(f"\n\nReceived {message_count} messages total")





asyncio.run(traffic())
