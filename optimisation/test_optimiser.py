"""
test_optimiser.py — Run this to verify your optimiser works.
Just run:  python test_optimiser.py
"""

from optimiser import TrafficSignalOptimiser

def print_recommendation(label, rec):
    print(f"\n{'='*60}")
    print(f"  SCENARIO: {label}")
    print(f"{'='*60}")
    if rec is None:
        print("  No recommendation produced.")
        return
    print(f"  Junction       : {rec.junction_id}")
    print(f"  Pattern        : {rec.pattern_type}")
    print(f"  Severity       : {rec.severity_score}")
    print(f"  Old cycle      : {rec.old_cycle_length}s")
    print(f"  New cycle      : {rec.new_cycle_length}s")
    print(f"  Old splits     : {rec.old_phase_splits}")
    print(f"  New splits     : {rec.new_phase_splits}")
    print(f"  Before queue   : {rec.before_max_queue} vehicles")
    print(f"  After est.     : {rec.after_est_queue} vehicles")
    print(f"  Before wait    : {rec.before_avg_wait}s")
    print(f"  After est.     : {rec.after_est_wait}s")
    print(f"  Improvement    : {rec.improvement_pct}%")
    print(f"  Explanation    : {rec.explanation}")


optimiser = TrafficSignalOptimiser()

# ── Test 1: Green waste ────────────────────────────────────────────────────────
e1 = {
    "junction_id":        "J14",
    "pattern_type":       "green_waste",
    "severity_score":     0.75,
    "queues":             {"north": 1, "south": 0, "east": 18, "west": 14},
    "active_phase":       "0",
    "phase_duration_total": 60,
    "explanation":        "Green lane nearly empty while others queue.",
}
print_recommendation("Green waste — empty green, busy red lanes", optimiser.optimise(e1))

# ── Test 2: Phase starvation ───────────────────────────────────────────────────
e2 = {
    "junction_id":        "J22",
    "pattern_type":       "phase_starvation",
    "severity_score":     0.85,
    "queues":             {"north": 17, "south": 4, "east": 3, "west": 4},
    "active_phase":       "1",
    "phase_duration_total": 60,
    "explanation":        "North queue growing — starved of green time.",
}
print_recommendation("Phase starvation — north queue growing", optimiser.optimise(e2))

# ── Test 3: Demand imbalance ───────────────────────────────────────────────────
e3 = {
    "junction_id":        "J07",
    "pattern_type":       "demand_imbalance",
    "severity_score":     0.65,
    "queues":             {"north": 3, "south": 2, "east": 22, "west": 1},
    "active_phase":       "0",
    "phase_duration_total": 60,
    "explanation":        "East has 22 vehicles, others have 1-3.",
}
print_recommendation("Demand imbalance — east overwhelmed", optimiser.optimise(e3))

# ── Test 4: Cycle too long ─────────────────────────────────────────────────────
e4 = {
    "junction_id":        "J03",
    "pattern_type":       "cycle_too_long",
    "severity_score":     0.7,
    "queues":             {"north": 8, "south": 6, "east": 5, "west": 7},
    "active_phase":       "0",
    "phase_duration_total": 150,
    "explanation":        "Cycle length 150s — too long.",
}
print_recommendation("Cycle too long — 150s cycle", optimiser.optimise(e4))

# ── Test 5: Low severity — should be skipped ───────────────────────────────────
e5 = {
    "junction_id":        "J01",
    "pattern_type":       "green_waste",
    "severity_score":     0.1,
    "queues":             {"north": 1, "south": 0},
    "active_phase":       "0",
    "phase_duration_total": 60,
    "explanation":        "Very minor issue.",
}
print_recommendation("Low severity — should still produce rec (worker filters)", optimiser.optimise(e5))

print(f"\n{'='*60}")
print("  ALL TESTS COMPLETE")
print(f"{'='*60}")
