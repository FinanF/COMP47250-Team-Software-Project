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
            "id": "1294004372",
            "lat": 53.34957,
            "lng": -6.253556,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GG",
            "approaches": [
                {
                    "lane_id": "4385842#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "4385842#0_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "1396454306",
            "lat": 53.348751,
            "lng": -6.25762,
            "current_phase": 0,
            "phase_duration_total": 60.0,
            "phase_duration_remaining": 42.0,
            "phase_duration_elapsed": 18.0,
            "signal_state": "GGrr",
            "approaches": [
                {
                    "lane_id": "529166768#1_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "125822009#0_0",
                    "queue_length": 1,
                    "waiting_time_avg": 7.5,
                    "vehicle_count": 2,
                    "green": False,
                    "seconds_since_green": 25.0
                }
            ]
        },
        {
            "id": "20447270",
            "lat": 53.353026,
            "lng": -6.25604,
            "current_phase": 0,
            "phase_duration_total": 45.0,
            "phase_duration_remaining": 40.0,
            "phase_duration_elapsed": 5.0,
            "signal_state": "GGgrrrGGrrr",
            "approaches": [
                {
                    "lane_id": "162745567#2_0",
                    "queue_length": 9,
                    "waiting_time_avg": 997.5,
                    "vehicle_count": 9,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "13904675#6_0",
                    "queue_length": 8,
                    "waiting_time_avg": 53.0,
                    "vehicle_count": 12,
                    "green": False,
                    "seconds_since_green": 10.0
                },
                {
                    "lane_id": "-37746962_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 1,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "-121166756#0_0",
                    "queue_length": 3,
                    "waiting_time_avg": 9.5,
                    "vehicle_count": 9,
                    "green": False,
                    "seconds_since_green": 10.0
                }
            ]
        },
        {
            "id": "2365997447",
            "lat": 53.352735,
            "lng": -6.261614,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "G",
            "approaches": [
                {
                    "lane_id": "4395952#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "26867633",
            "lat": 53.351366,
            "lng": -6.263697,
            "current_phase": 2,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 35.0,
            "signal_state": "GGGrrr",
            "approaches": [
                {
                    "lane_id": "-26143790#1_0",
                    "queue_length": 2,
                    "waiting_time_avg": 68.5,
                    "vehicle_count": 2,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "4395994#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "-4395994#3_0",
                    "queue_length": 5,
                    "waiting_time_avg": 215.5,
                    "vehicle_count": 5,
                    "green": False,
                    "seconds_since_green": 40.0
                }
            ]
        },
        {
            "id": "26867646",
            "lat": 53.351891,
            "lng": -6.262886,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GGGG",
            "approaches": [
                {
                    "lane_id": "12341238#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "12341238#0_1",
                    "queue_length": 11,
                    "waiting_time_avg": 875.0,
                    "vehicle_count": 11,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "-4395994#1_0",
                    "queue_length": 8,
                    "waiting_time_avg": 683.0,
                    "vehicle_count": 8,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "2892088923",
            "lat": 53.348327,
            "lng": -6.259752,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GGG",
            "approaches": [
                {
                    "lane_id": "3787955#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "3787955#0_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "3451922932",
            "lat": 53.352555,
            "lng": -6.261345,
            "current_phase": 2,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 35.0,
            "signal_state": "rGG",
            "approaches": [
                {
                    "lane_id": "3957139#1_0",
                    "queue_length": 2,
                    "waiting_time_avg": 436.0,
                    "vehicle_count": 2,
                    "green": False,
                    "seconds_since_green": 40.0
                },
                {
                    "lane_id": "578973715#0_0",
                    "queue_length": 2,
                    "waiting_time_avg": 168.5,
                    "vehicle_count": 2,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "578973715#0_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "3451922950",
            "lat": 53.352354,
            "lng": -6.261498,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GG",
            "approaches": [
                {
                    "lane_id": "192108786#1_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 1,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "192108786#1_1",
                    "queue_length": 5,
                    "waiting_time_avg": 1177.0,
                    "vehicle_count": 5,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "3594514234",
            "lat": 53.349041,
            "lng": -6.254673,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GG",
            "approaches": [
                {
                    "lane_id": "41851537#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "41851537#0_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "3621526490",
            "lat": 53.352749,
            "lng": -6.261428,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GGG",
            "approaches": [
                {
                    "lane_id": "37692415#0_0",
                    "queue_length": 2,
                    "waiting_time_avg": 148.5,
                    "vehicle_count": 2,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "37692415#0_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "5029099782",
            "lat": 53.347976,
            "lng": -6.257353,
            "current_phase": 2,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 35.0,
            "signal_state": "rrrGGGG",
            "approaches": [
                {
                    "lane_id": "14047774#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 1,
                    "green": False,
                    "seconds_since_green": 40.0
                }
            ]
        },
        {
            "id": "511114288",
            "lat": 53.348446,
            "lng": -6.259528,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GGG",
            "approaches": [
                {
                    "lane_id": "49961184#2_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 1,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "49961184#2_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "5300228178",
            "lat": 53.352392,
            "lng": -6.261273,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GG",
            "approaches": [
                {
                    "lane_id": "3788405#0_0",
                    "queue_length": 1,
                    "waiting_time_avg": 82.5,
                    "vehicle_count": 1,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "3788405#0_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "5300250107",
            "lat": 53.349785,
            "lng": -6.260397,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GG",
            "approaches": [
                {
                    "lane_id": "677070805#4_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "677070805#4_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 1,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "5300250108",
            "lat": 53.349819,
            "lng": -6.260128,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GG",
            "approaches": [
                {
                    "lane_id": "49961189#2_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "49961189#2_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "5301488751",
            "lat": 53.35201,
            "lng": -6.261362,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GG",
            "approaches": [
                {
                    "lane_id": "3788404#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "3788404#0_1",
                    "queue_length": 25,
                    "waiting_time_avg": 3327.5,
                    "vehicle_count": 26,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "659815",
            "lat": 53.350741,
            "lng": -6.254409,
            "current_phase": 2,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 35.0,
            "signal_state": "rrGGGrr",
            "approaches": [
                {
                    "lane_id": "43100899#0_0",
                    "queue_length": 4,
                    "waiting_time_avg": 589.5,
                    "vehicle_count": 4,
                    "green": False,
                    "seconds_since_green": 40.0
                },
                {
                    "lane_id": "43100899#0_1",
                    "queue_length": 11,
                    "waiting_time_avg": 1564.5,
                    "vehicle_count": 11,
                    "green": False,
                    "seconds_since_green": 40.0
                },
                {
                    "lane_id": "584286613_0",
                    "queue_length": 10,
                    "waiting_time_avg": 813.0,
                    "vehicle_count": 10,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "-162745567#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": False,
                    "seconds_since_green": 40.0
                }
            ]
        },
        {
            "id": "710547269",
            "lat": 53.354182,
            "lng": -6.256868,
            "current_phase": 6,
            "phase_duration_total": 24.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 17.0,
            "signal_state": "rrrrGGGGrr",
            "approaches": [
                {
                    "lane_id": "37746962_0",
                    "queue_length": 17,
                    "waiting_time_avg": 2056.0,
                    "vehicle_count": 17,
                    "green": False,
                    "seconds_since_green": 20.0
                },
                {
                    "lane_id": "440034441#1_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 1,
                    "green": False,
                    "seconds_since_green": 30.0
                },
                {
                    "lane_id": "440034441#1_1",
                    "queue_length": 2,
                    "waiting_time_avg": 207.0,
                    "vehicle_count": 3,
                    "green": False,
                    "seconds_since_green": 60.0
                },
                {
                    "lane_id": "-37692198#1_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "-37692198#1_1",
                    "queue_length": 8,
                    "waiting_time_avg": 1764.5,
                    "vehicle_count": 8,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "192108787#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "192108787#0_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": False,
                    "seconds_since_green": 30.0
                }
            ]
        },
        {
            "id": "cluster_1277707259_1415538921_668804488",
            "lat": 53.353825,
            "lng": -6.2584,
            "current_phase": 2,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 35.0,
            "signal_state": "GGgrrrGGgrrr",
            "approaches": [
                {
                    "lane_id": "14047759#0_0",
                    "queue_length": 3,
                    "waiting_time_avg": 421.5,
                    "vehicle_count": 3,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "-192108787#1_0",
                    "queue_length": 10,
                    "waiting_time_avg": 1368.5,
                    "vehicle_count": 10,
                    "green": False,
                    "seconds_since_green": 40.0
                },
                {
                    "lane_id": "-112410779#0_0",
                    "queue_length": 8,
                    "waiting_time_avg": 646.5,
                    "vehicle_count": 8,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "52881850#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": False,
                    "seconds_since_green": 40.0
                }
            ]
        },
        {
            "id": "cluster_1294004359_1294004382",
            "lat": 53.349644,
            "lng": -6.253738,
            "current_phase": 2,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 35.0,
            "signal_state": "GGGG",
            "approaches": [
                {
                    "lane_id": "-3789702_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "515236648#0_0",
                    "queue_length": 9,
                    "waiting_time_avg": 823.5,
                    "vehicle_count": 9,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "515236648#0_1",
                    "queue_length": 9,
                    "waiting_time_avg": 1090.0,
                    "vehicle_count": 9,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "cluster_20299832_527734964_537784305",
            "lat": 53.355724,
            "lng": -6.258016,
            "current_phase": 4,
            "phase_duration_total": 37.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 30.0,
            "signal_state": "rrrGGgrrrGGg",
            "approaches": [
                {
                    "lane_id": "37692198#2_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 1,
                    "green": False,
                    "seconds_since_green": 45.0
                },
                {
                    "lane_id": "-3936660#1_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "cluster_2418681455_3772654578",
            "lat": 53.349167,
            "lng": -6.255095,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "G",
            "approaches": [
                {
                    "lane_id": "529166764#0_0",
                    "queue_length": 3,
                    "waiting_time_avg": 25.5,
                    "vehicle_count": 5,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "cluster_3260618602_389365",
            "lat": 53.354496,
            "lng": -6.263496,
            "current_phase": 2,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 35.0,
            "signal_state": "GrrrGG",
            "approaches": [
                {
                    "lane_id": "-3979042#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "37692391#0_0",
                    "queue_length": 14,
                    "waiting_time_avg": 710.0,
                    "vehicle_count": 14,
                    "green": False,
                    "seconds_since_green": 40.0
                },
                {
                    "lane_id": "49961188#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        },
        {
            "id": "cluster_336173796_389292",
            "lat": 53.348364,
            "lng": -6.254946,
            "current_phase": 4,
            "phase_duration_total": 37.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 30.0,
            "signal_state": "GGGGGrrrrrr",
            "approaches": [
                {
                    "lane_id": "3787451_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "3787451_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "3787451_2",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "3787451_3",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "229727179_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": False,
                    "seconds_since_green": 45.0
                },
                {
                    "lane_id": "229727179_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": False,
                    "seconds_since_green": 45.0
                },
                {
                    "lane_id": "506780986_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": False,
                    "seconds_since_green": 35.0
                },
                {
                    "lane_id": "506780986_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": False,
                    "seconds_since_green": 35.0
                }
            ]
        },
        {
            "id": "cluster_3451922931_3621526491_5301585467_5301585472",
            "lat": 53.352735,
            "lng": -6.261167,
            "current_phase": 0,
            "phase_duration_total": 82.0,
            "phase_duration_remaining": 2.0,
            "phase_duration_elapsed": 80.0,
            "signal_state": "GGG",
            "approaches": [
                {
                    "lane_id": "-548793704#1_0",
                    "queue_length": 10,
                    "waiting_time_avg": 1468.0,
                    "vehicle_count": 10,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "356748752#0_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
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
            "id": "cluster_5300250112_5301488754",
            "lat": 53.351998,
            "lng": -6.261099,
            "current_phase": 2,
            "phase_duration_total": 42.0,
            "phase_duration_remaining": 7.0,
            "phase_duration_elapsed": 35.0,
            "signal_state": "rGGG",
            "approaches": [
                {
                    "lane_id": "-52879958_0",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": False,
                    "seconds_since_green": 40.0
                },
                {
                    "lane_id": "3788405#1_0",
                    "queue_length": 6,
                    "waiting_time_avg": 553.0,
                    "vehicle_count": 6,
                    "green": True,
                    "seconds_since_green": 0.0
                },
                {
                    "lane_id": "3788405#1_1",
                    "queue_length": 0,
                    "waiting_time_avg": 0.0,
                    "vehicle_count": 0,
                    "green": True,
                    "seconds_since_green": 0.0
                }
            ]
        }
    ]
}
events = detector.analyse(s6)
print_events("Real data", events)

print("\n" + "="*60)
print("  ALL TESTS COMPLETE")
print("="*60)
