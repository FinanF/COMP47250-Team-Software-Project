"""
test_engine.py — Run this to demo the DiagnosticEngine with mock data.
This is what you show in your video and interim demo.

Run with:  python test_engine.py
"""

from engine import DiagnosticEngine


def print_events(label, events):
    print(f"\n{'='*60}")
    print(f"  SCENARIO: {label}")
    print(f"{'='*60}")
    if not events:
        print("  No congestion detected.")
    for e in events:
        print(f"\n  Pattern     : {e.pattern_type.upper()}")
        print(f"  Junction    : {e.junction_id}")
        print(f"  Severity    : {e.severity_score}")
        print(f"  Explanation : {e.explanation}")
        print(f"  Queues      : {e.queues}")


if __name__ == "__main__":
    engine = DiagnosticEngine()

    # ── Scenario 1: Green Phase Waste ──────────────────────────────────────────
    # North-south phase is green but north/south barely have any vehicles.
    # Meanwhile east and west are heavily backed up.
    s1 = {
        "junction_id":            "J_001",
        "timestamp":              "2026-06-17T09:00:00",
        "queues":                 {"north": 1, "south": 0, "east": 18, "west": 14},
        "active_phase":           "north_south",
        "phase_duration_elapsed": 22,
        "phase_duration_total":   30,
    }
    events = engine.analyse(s1)
    print_events("Green Phase Waste — green on empty north/south while east/west queues", events)

    # ── Scenario 2: Demand Imbalance ───────────────────────────────────────────
    # East has 22 vehicles, west has 1 — huge imbalance on the same phase axis.
    s2 = {
        "junction_id":            "J_002",
        "timestamp":              "2026-06-17T09:01:00",
        "queues":                 {"north": 3, "south": 2, "east": 22, "west": 1},
        "active_phase":           "north_south",
        "phase_duration_elapsed": 10,
        "phase_duration_total":   30,
    }
    events = engine.analyse(s2)
    print_events("Demand Imbalance — east has 22x more vehicles than west", events)

    # ── Scenario 3: Phase Starvation ───────────────────────────────────────────
    # West direction queue is growing across 4 consecutive readings.
    # Need to feed the engine multiple states to build history.
    starvation_states = [
        {"junction_id": "J_003", "timestamp": "2026-06-17T09:02:00",
         "queues": {"north": 5, "south": 4, "east": 3, "west": 5},
         "active_phase": "north_south", "phase_duration_elapsed": 5, "phase_duration_total": 30},
        {"junction_id": "J_003", "timestamp": "2026-06-17T09:02:30",
         "queues": {"north": 5, "south": 4, "east": 3, "west": 8},
         "active_phase": "north_south", "phase_duration_elapsed": 10, "phase_duration_total": 30},
        {"junction_id": "J_003", "timestamp": "2026-06-17T09:03:00",
         "queues": {"north": 5, "south": 4, "east": 3, "west": 12},
         "active_phase": "north_south", "phase_duration_elapsed": 15, "phase_duration_total": 30},
        {"junction_id": "J_003", "timestamp": "2026-06-17T09:03:30",
         "queues": {"north": 5, "south": 4, "east": 3, "west": 17},
         "active_phase": "north_south", "phase_duration_elapsed": 20, "phase_duration_total": 30},
    ]

    all_events = []
    for s in starvation_states:
        all_events = engine.analyse(s)

    print_events("Phase Starvation — west queue growing 5→8→12→17 while stuck on red", all_events)

    # ── Scenario 4: No congestion (normal traffic) ─────────────────────────────
    s4 = {
        "junction_id":            "J_004",
        "timestamp":              "2026-06-17T09:04:00",
        "queues":                 {"north": 2, "south": 3, "east": 1, "west": 2},
        "active_phase":           "north_south",
        "phase_duration_elapsed": 10,
        "phase_duration_total":   30,
    }
    events = engine.analyse(s4)
    print_events("Normal Traffic — no congestion expected", events)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  FEATURE EXTRACTION (what the ML model will use)")
    print(f"{'='*60}")
    features = engine.extract_features(s1)
    for k, v in features.items():
        print(f"  {k:25s}: {v:.2f}" if isinstance(v, float) else f"  {k:25s}: {v}")
