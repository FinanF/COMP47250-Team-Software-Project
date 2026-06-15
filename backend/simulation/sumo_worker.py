import asyncio
import json
import os
import sys
import xml.etree.ElementTree as ET
import traci

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUMO_BINARY = "sumo"
SUMO_CONFIG = os.path.join(BASE_DIR, "dublin_sub.sumocfg")
NET_XML = os.path.join(BASE_DIR, "dublin_sub.net.xml")

SCHEMA_VERSION = "1.1"
EMIT_EVERY_N_STEPS = 10   # emit every 10 steps = every 5 sim-seconds at 0.5s step
MAX_SIM_TIME = 3600.0     # 1 hour of simulation time
STEP_LENGTH = 0.5         # must match <step-length> in .sumocfg

pending_changes: dict = {}
_last_green_time: dict = {}

def parse_junction_coordinates(net_xml_path: str) -> dict:

    coords = {}
    try:
        tree = ET.parse(net_xml_path)
        root = tree.getroot()

        # Extract the network offset and projection for coordinate conversion
        location = root.find("location")
        if location is None:
            print("[WARN] No <location> element in .net.xml — coordinates may be off",
                  file=sys.stderr)

        for junction in root.findall("junction"):
            jid = junction.get("id")
            jtype = junction.get("type")

            # Skip internal junctions (":cluster_..." style) — only real TLS junctions
            if jtype == "internal" or jid is None:
                continue

            x = junction.get("x")
            y = junction.get("y")
            if x is None or y is None:
                continue

            coords[jid] = {"x": float(x), "y": float(y)}

    except Exception as e:
        print(f"[ERROR] Failed to parse {net_xml_path}: {e}", file=sys.stderr)

    return coords


async def seed_junction_table(db_queue: asyncio.Queue, net_xml_path: str) -> list:

    raw_coords = parse_junction_coordinates(net_xml_path)
    tls_ids = set(traci.trafficlight.getIDList())

    junctions = []
    for jid, pos in raw_coords.items():
        if jid not in tls_ids:
            continue  # only seed signalised junctions
        try:
            lon, lat = traci.simulation.convertGeo(pos["x"], pos["y"])
            junctions.append({
                "id": jid,
                "lat": round(lat, 6),
                "lng": round(lon, 6)
            })
        except Exception as e:
            print(f"[WARN] convertGeo failed for {jid}: {e}", file=sys.stderr)

    # Push a seed message to Finan's DB worker
    await db_queue.put({
        "type": "seed_junctions",
        "junctions": junctions
    })

    print(f"[SIM] Seeded {len(junctions)} junctions into DB queue", file=sys.stderr)
    return junctions


def get_junction_state(tls_id: str, sim_time: float) -> dict:
    global _last_green_time

    phase = traci.trafficlight.getPhase(tls_id)
    phase_duration = traci.trafficlight.getPhaseDuration(tls_id)
    signal_state = traci.trafficlight.getRedYellowGreenState(tls_id)

    # getNextSwitch() returns the sim time when the current phase ends
    next_switch = traci.trafficlight.getNextSwitch(tls_id)
    phase_duration_remaining = round(next_switch - sim_time, 1)

    # getControlledLinks() returns one entry per signal index, matching signal_state
    # Each entry is a list of (from_lane, to_lane, via) tuples
    controlled_links = traci.trafficlight.getControlledLinks(tls_id)

    # Aggregate per incoming lane
    # A lane can have multiple links (e.g. straight + left turn)
    # The lane is green if ANY of its signal indices is 'g' or 'G'
    lane_states: dict = {}

    for i, link_list in enumerate(controlled_links):
        if not link_list:
            continue

        from_lane = link_list[0][0]  # incoming lane ID
        is_green = signal_state[i].lower() == 'g' if i < len(signal_state) else False

        if from_lane not in lane_states:
            try:
                queue = traci.lane.getLastStepHaltingNumber(from_lane)
                waiting = traci.lane.getWaitingTime(from_lane)
                vehicles = traci.lane.getLastStepVehicleNumber(from_lane)
            except traci.exceptions.TraCIException:
                # Lane may not exist in subnetwork — skip silently
                continue

            # Track last green time for starvation detection
            if is_green:
                _last_green_time[from_lane] = sim_time

            last_green = _last_green_time.get(from_lane)
            seconds_since_green = (
                round(sim_time - last_green, 1) if last_green is not None else None
            )

            lane_states[from_lane] = {
                "lane_id": from_lane,
                "queue_length": queue,
                "waiting_time_avg": round(waiting, 2),
                "vehicle_count": vehicles,
                "green": is_green,
                "seconds_since_green": seconds_since_green
            }
        else:
            # Update green status — if any link is green, the lane is green
            if is_green:
                lane_states[from_lane]["green"] = True
                _last_green_time[from_lane] = sim_time
                lane_states[from_lane]["seconds_since_green"] = 0.0

    x, y = traci.junction.getPosition(tls_id)
    lon, lat = traci.simulation.convertGeo(x, y)

    return {
        "id": tls_id,
        "lat": round(lat, 6),
        "lng": round(lon, 6),
        "current_phase": phase,
        "phase_duration_total": phase_duration,
        "phase_duration_remaining": phase_duration_remaining,
        "signal_state": signal_state,
        "approaches": list(lane_states.values())
    }


def apply_pending_changes():
    global pending_changes
    if not pending_changes:
        return

    for junction_id, new_program in list(pending_changes.items()):
        try:
            traci.trafficlight.setCompleteRedYellowGreenDefinition(
                junction_id, new_program
            )
            print(f"[SIM] Applied new signal program to {junction_id}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Failed to apply change to {junction_id}: {e}",
                  file=sys.stderr)

    pending_changes.clear()


async def sumo_worker(
    traffic_queue: asyncio.Queue,
    db_queue: asyncio.Queue,
    shutdown_event: asyncio.Event
):
    print(f"[SIM] Starting SUMO — config: {SUMO_CONFIG}", file=sys.stderr)
    print(f"[SIM] SUMO_HOME: {os.environ.get('SUMO_HOME', 'NOT SET')}", file=sys.stderr)
    print(f"[SIM] Config exists: {os.path.exists(SUMO_CONFIG)}", file=sys.stderr)
    print(f"[SIM] NET_XML exists: {os.path.exists(NET_XML)}", file=sys.stderr)

    try:
        traci.start([
            SUMO_BINARY,
            "-c", SUMO_CONFIG,
            "--no-warnings",
            "--duration-log.disable", "true",
            f"--step-length", str(STEP_LENGTH)
        ])
    except Exception as e:
        print(f"[ERROR] traci.start() failed: {e}", file=sys.stderr)
        shutdown_event.set()
        return

    tls_ids = traci.trafficlight.getIDList()
    print(f"[SIM] Found {len(tls_ids)} signalised junctions", file=sys.stderr)

    # Seed junction coordinates into DB before first emit
    try:
        await seed_junction_table(db_queue, NET_XML)
    except Exception as e:
        print(f"[WARN] Junction seeding failed: {e}", file=sys.stderr)

    step = 0

    try:
        while (
            not shutdown_event.is_set()
            and traci.simulation.getTime() < MAX_SIM_TIME
        ):
            # Apply any operator-approved signal changes before stepping
            apply_pending_changes()

            # Advance simulation by one step (STEP_LENGTH seconds)
            traci.simulationStep()
            step += 1

            # Yield control to the event loop so fastapi stays responsive
            await asyncio.sleep(0)

            if step % EMIT_EVERY_N_STEPS != 0:
                continue

            sim_time = traci.simulation.getTime()
            junctions = []
            failures = 0

            for tls_id in tls_ids:
                try:
                    junctions.append(get_junction_state(tls_id, sim_time))
                except Exception as e:
                    failures += 1
                    print(f"[WARN] State extraction failed for {tls_id}: {e}",
                          file=sys.stderr)

            if failures == len(tls_ids):
                print("[ERROR] All junction extractions failed — stopping simulation",
                      file=sys.stderr)
                break

            # Determine simulation status for consumers
            time_remaining = MAX_SIM_TIME - sim_time
            if sim_time < 60:
                sim_status = "warmup"
            elif time_remaining < 60:
                sim_status = "ending"
            else:
                sim_status = "running"

            state = {
                "schema_version": SCHEMA_VERSION,
                "step": step,
                "timestamp": round(sim_time, 1),
                "junction_count": len(junctions),
                "sim_status": sim_status,
                "sim_time_remaining": round(time_remaining, 1),
                "junctions": junctions
            }

            # Non-blocking put — drop the frame if queue is full rather than stalling
            try:
                traffic_queue.put_nowait(state)
            except asyncio.QueueFull:
                print(f"[WARN] traffic_queue full at step {step} — frame dropped",
                      file=sys.stderr)

            print(
                f"[SIM] Step {step} | "
                f"Sim {sim_time:.1f}s | "
                f"{len(junctions)} junctions | "
                f"status={sim_status}",
                file=sys.stderr
            )

        print(f"[SIM] Simulation ended after {step} steps "
              f"({traci.simulation.getTime():.1f}s sim time)", file=sys.stderr)

    except Exception as e:
        print(f"[ERROR] Simulation loop crashed: {e}", file=sys.stderr)

    finally:
        traci.close()
        print("[SIM] TraCI closed", file=sys.stderr)
        shutdown_event.set()


async def _standalone_test():
    traffic_queue = asyncio.Queue(maxsize=50)
    db_queue = asyncio.Queue(maxsize=50)
    shutdown_event = asyncio.Event()

    # Launch worker as a background task
    worker_task = asyncio.create_task(
        sumo_worker(traffic_queue, db_queue, shutdown_event)
    )

    # Consumer: print traffic states as they arrive
    frames_received = 0
    while not shutdown_event.is_set() or not traffic_queue.empty():
        try:
            state = await asyncio.wait_for(traffic_queue.get(), timeout=2.0)
            print(json.dumps(state, indent=2))
            frames_received += 1

            # Stop after 20 frames for quick local testing
            if frames_received >= 100:
                shutdown_event.set()
                break

        except asyncio.TimeoutError:
            if shutdown_event.is_set():
                break

    await worker_task
    print(f"\n[TEST] Received {frames_received} frames. Schema looks good.",
          file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(_standalone_test())
