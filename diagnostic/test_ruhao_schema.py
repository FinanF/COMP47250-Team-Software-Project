"""
test_ruhao_schema.py — Test rules.py against Ruhao's actual SUMO schema.
"""
import sys
sys.path.insert(0, '.')

# Use the updated rules
import importlib.util, types

# Load rules_v2 as rules
spec = importlib.util.spec_from_file_location("rules", "rules.py")
rules_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules_mod)
RuleBasedDetector = rules_mod.RuleBasedDetector

def print_events(label, events):
    print(f"\n{'='*60}")
    print(f"  SCENARIO: {label}")
    print(f"{'='*60}")
    if not events:
        print("  No congestion detected. CORRECT")
        return
    for e in events:
        print(f"\n  Pattern     : {e.pattern_type.upper()}")
        print(f"  Junction    : {e.junction_id}")
        print(f"  Severity    : {e.severity_score}")
        print(f"  Explanation : {e.explanation}")

detector = RuleBasedDetector()

# Scenario 1: Green waste — green lane has 0 vehicles, red lane has 12
s1 = {
    "type": "junction_state",
    "id": "cluster_5300250112_5301488754",
    "lat": 53.351998,
    "lng": -6.261099,
    "current_phase": 0,
    "phase_duration_total": 42.0,
    "phase_duration_remaining": 20.0,
    "signal_state": "GGrr",
    "approaches": [
        {"lane_id": "3788405#1_0", "queue_length": 0,  "waiting_time_avg": 0.0,  "vehicle_count": 0, "green": True,  "seconds_since_green": 5.0},
        {"lane_id": "3788405#1_1", "queue_length": 1,  "waiting_time_avg": 2.0,  "vehicle_count": 1, "green": True,  "seconds_since_green": 5.0},
        {"lane_id": "9876543#0_0", "queue_length": 12, "waiting_time_avg": 45.0, "vehicle_count": 8, "green": False, "seconds_since_green": 37.0},
        {"lane_id": "9876543#0_1", "queue_length": 8,  "waiting_time_avg": 30.0, "vehicle_count": 5, "green": False, "seconds_since_green": 37.0},
    ]
}
events = detector.analyse(s1)
print_events("Green Waste — green lane empty, red lanes backed up", events)

# Scenario 2: Demand imbalance — one lane has 18 vehicles, others have 1
s2 = {
    "type": "junction_state",
    "id": "cluster_1234_5678",
    "lat": 53.35,
    "lng": -6.26,
    "current_phase": 1,
    "phase_duration_total": 60.0,
    "phase_duration_remaining": 30.0,
    "signal_state": "rrGG",
    "approaches": [
        {"lane_id": "111#0_0", "queue_length": 1,  "waiting_time_avg": 5.0,  "vehicle_count": 1, "green": False, "seconds_since_green": 20.0},
        {"lane_id": "111#0_1", "queue_length": 1,  "waiting_time_avg": 5.0,  "vehicle_count": 1, "green": False, "seconds_since_green": 20.0},
        {"lane_id": "222#0_0", "queue_length": 18, "waiting_time_avg": 60.0, "vehicle_count": 12,"green": True,  "seconds_since_green": 0.0},
        {"lane_id": "222#0_1", "queue_length": 2,  "waiting_time_avg": 8.0,  "vehicle_count": 2, "green": True,  "seconds_since_green": 0.0},
    ]
}
events = detector.analyse(s2)
print_events("Demand Imbalance — lane 222#0_0 has 18x more than others", events)

# Scenario 3: Phase starvation — feed 4 readings with growing queue on red lane
base = {
    "type": "junction_state",
    "id": "cluster_9999_8888",
    "lat": 53.34,
    "lng": -6.25,
    "current_phase": 0,
    "phase_duration_total": 45.0,
    "signal_state": "GGrr",
}
queue_growth = [5, 8, 12, 17]
for i, q in enumerate(queue_growth):
    state = {**base,
        "phase_duration_remaining": 45.0 - (i * 5),
        "approaches": [
            {"lane_id": "green#0_0", "queue_length": 3,  "green": True,  "seconds_since_green": i*5, "waiting_time_avg": 0, "vehicle_count": 3},
            {"lane_id": "red#0_0",   "queue_length": q,  "green": False, "seconds_since_green": i*10,"waiting_time_avg": q*3,"vehicle_count": q},
        ]
    }
    events = detector.analyse(state)

print_events(f"Phase Starvation — red#0_0 queue grew {queue_growth}", events)

# Scenario 4: Non junction_state message — should be ignored
s4 = {
    "type": "vehicle_positions",
    "vehicles": [{"id": "v1", "lat": 53.35, "lng": -6.26}]
}
events = detector.analyse(s4)
print_events("Vehicle positions message — should be ignored", events)

# Scenario 5: Normal traffic — no congestion
s5 = {
    "type": "junction_state",
    "id": "cluster_normal",
    "lat": 53.35, "lng": -6.26,
    "current_phase": 0,
    "phase_duration_total": 42.0,
    "phase_duration_remaining": 20.0,
    "signal_state": "GGrr",
    "approaches": [
        {"lane_id": "a#0_0", "queue_length": 2, "green": True,  "seconds_since_green": 5, "waiting_time_avg": 3, "vehicle_count": 2},
        {"lane_id": "b#0_0", "queue_length": 1, "green": False, "seconds_since_green": 15,"waiting_time_avg": 2, "vehicle_count": 1},
    ]
}
events = detector.analyse(s5)
print_events("Normal Traffic — no congestion expected", events)

s6={
    "type": "junction_state",
    "schema_version": "1.2",
    "step": 3040,
    "timestamp": 1520.0,
    "junction_count": 28,
    "sim_status": "running",
    "sim_time_remaining": 2080.0,
    "junctions": [
            {
            "type": "junction_state",
            "id": "Finan test",
            "lat": 53.352354,
            "lng": -6.261498,
            "current_phase": 1,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 40.0,
            "phase_duration_elapsed": 42.0,
            "signal_state": "GGrr",
            "approaches": [
                {
                    "lane_id": "192108786#1_0",
                    "queue_length": 30,
                    "waiting_time_avg": 120.0,
                    "vehicle_count": 30,
                    "green": False,
                    "seconds_since_green": 40.0
                },
                {
                    "lane_id": "192108786#1_1",
                    "queue_length": 3,
                    "waiting_time_avg": 8.0,
                    "vehicle_count": 3,
                    "green": False,
                    "seconds_since_green": 40.0
                },
                {
                    "lane_id": "192108786#2_0",
                    "queue_length": 2,
                    "waiting_time_avg": 5.0,
                    "vehicle_count": 2,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "192108786#2_1",
                    "queue_length": 1,
                    "waiting_time_avg": 2.0,
                    "vehicle_count": 1,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "cluster_389364_5403869166",
            "lat": 53.353612,
            "lng": -6.265583,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GGGG",
            "approaches": [
                {
                    "lane_id": "338075835#0_0",
                    "queue_length": 23,
                    "waiting_time_avg": 826.5,
                    "vehicle_count": 24,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "338075835#0_1",
                    "queue_length": 31,
                    "waiting_time_avg": 1300.5,
                    "vehicle_count": 32,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "338075835#0_2",
                    "queue_length": 31,
                    "waiting_time_avg": 1902.0,
                    "vehicle_count": 32,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "type": "junction_state",
            "id": "cluster_5300250112_5301488754",
            "lat": 53.351998,
            "lng": -6.261099,
            "current_phase": 0,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 20.0,
            "signal_state": "GGrr",
            "approaches": [
                {"lane_id": "3788405#1_0", "queue_length": 0, "waiting_time_avg": 0.0, "vehicle_count": 0,
                 "green": True, "seconds_since_green": 5.0},
                {"lane_id": "3788405#1_1", "queue_length": 1, "waiting_time_avg": 2.0, "vehicle_count": 1,
                 "green": True, "seconds_since_green": 5.0},
                {"lane_id": "9876543#0_0", "queue_length": 12, "waiting_time_avg": 45.0, "vehicle_count": 8,
                 "green": False, "seconds_since_green": 37.0},
                {"lane_id": "9876543#0_1", "queue_length": 8, "waiting_time_avg": 30.0, "vehicle_count": 5,
                 "green": False, "seconds_since_green": 37.0},
            ]
        }
    ]
}
for junction in s6["junctions"]:
    detector=RuleBasedDetector()
    events = detector.analyse(junction)
    print_events(f"{junction['id']} Real data", events)
    print(junction)

print("\n" + "="*60)
print("  ALL TESTS COMPLETE")
print("="*60)
