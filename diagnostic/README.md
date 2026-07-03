# Diagnostic Algorithm

Detects congestion patterns caused by poor traffic signal timing.

## Two-layer architecture

**Layer 1 — Rule-based detector** (rules.py)
Detects: green_waste, phase_starvation, demand_imbalance, cycle_too_long
No training data required. Runs immediately.

**Layer 2 — ML classifier** (engine.py)
Model: Random Forest (100 estimators)
Trained on: ground_truth.csv from SUMO simulation (1400 rows)
Classes: normal, green_waste, starvation, demand_imbalance
Results: Precision 0.96 | Recall 0.65 | F1 0.75

## How to run

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python train_classifier.py
    python test_engine.py

## Output format

Every detection emits a CongestionEvent with:
- junction_id
- pattern_type
- severity_score (0.0 to 1.0)
- explanation (plain English)
- queues (snapshot)
- detected_at (timestamp)
