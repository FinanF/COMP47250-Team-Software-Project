import traci
import json
import os

# Portable — works on any machine
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUMO_BINARY = "sumo"
SUMO_CONFIG = os.path.join(BASE_DIR, "dublin_sub.sumocfg")

EMIT_EVERY_N_STEPS = 10
MAX_STEPS = 200

def get_junction_state(tls_id: str) -> dict:
    phase = traci.trafficlight.getPhase(tls_id)
    phase_duration = traci.trafficlight.getPhaseDuration(tls_id)
    signal_state = traci.trafficlight.getRedYellowGreenState(tls_id)
    controlled_lanes = list(set(traci.trafficlight.getControlledLanes(tls_id)))

    approaches = []
    for i, lane in enumerate(controlled_lanes):
        queue = traci.lane.getLastStepHaltingNumber(lane)
        waiting = traci.lane.getWaitingTime(lane)
        vehicles = traci.lane.getLastStepVehicleNumber(lane)
        green = signal_state[i].lower() == 'g' if i < len(signal_state) else False

        approaches.append({
            "lane_id": lane,
            "queue_length": queue,
            "waiting_time_avg": round(waiting, 2),
            "vehicle_count": vehicles,
            "green": green
        })

    x, y = traci.junction.getPosition(tls_id)
    lon, lat = traci.simulation.convertGeo(x, y)

    return {
        "id": tls_id,
        "lat": round(lat, 6),
        "lng": round(lon, 6),
        "current_phase": phase,
        "phase_duration_total": phase_duration,
        "signal_state": signal_state,
        "approaches": approaches
    }


def emit_state(tls_ids: list, step: int):
    junctions = []
    for tls_id in tls_ids:
        try:
            junctions.append(get_junction_state(tls_id))
        except Exception as e:
            print(f"[WARN] {tls_id}: {e}")

    state = {
        "step": step,
        "timestamp": round(traci.simulation.getTime(), 1),
        "junction_count": len(junctions),
        "junctions": junctions
    }

    print(json.dumps(state, indent=2))
    print(f"--- Step {step} | Sim time {state['timestamp']}s ---\n")


def run():
    print("Starting SUMO with subnetwork...")
    print(f"Config: {SUMO_CONFIG}")

    traci.start([
        SUMO_BINARY,
        "-c", SUMO_CONFIG,
        "--end", "3600",
        "--no-warnings",
        "--duration-log.disable", "true"
    ])

    tls_ids = traci.trafficlight.getIDList()
    print(f"Found {len(tls_ids)} signalised junctions\n")

    step = 0
    try:
        while traci.simulation.getMinExpectedNumber() > 0 and step < MAX_STEPS:
            traci.simulationStep()
            step += 1

            if step % EMIT_EVERY_N_STEPS == 0:
                emit_state(tls_ids, step)

        print(f"Test complete after {step} steps.")

    finally:
        traci.close()
        print("TraCI closed.")


if __name__ == "__main__":
    run()
