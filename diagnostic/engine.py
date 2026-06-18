"""
engine.py — DiagnosticEngine
Combines Layer 1 (rule-based) and Layer 2 (ML classifier).
Pure Python — no asyncio here. The worker wraps this.
"""

from rules import RuleBasedDetector, CongestionEvent
import pandas as pd
import numpy as np


class DiagnosticEngine:
    """
    Main engine. Call analyse(state) on every incoming traffic state.
    Returns a list of CongestionEvent objects.

    Layer 1 — RuleBasedDetector  : fast, always runs, no training needed
    Layer 2 — MLClassifier       : catches subtler patterns, needs training data
                                   (disabled until you train it in Week 7)
    """

    def __init__(self, ml_model=None):
        self.rule_detector = RuleBasedDetector()
        self.ml_model      = ml_model   # None until trained
        self._state_buffer = []         # collects states for ML training data

    def analyse(self, state: dict) -> list[CongestionEvent]:
        """
        Main entry point. Returns all detected congestion events for this state.
        """
        events = []

        # Layer 1 — always runs
        rule_events = self.rule_detector.analyse(state)
        events.extend(rule_events)

        # Layer 2 — only runs once model is trained
        if self.ml_model is not None:
            ml_events = self._ml_classify(state, rule_events)
            # Only add ML events that weren't already caught by rules
            existing_patterns = {e.pattern_type for e in rule_events}
            for e in ml_events:
                if e.pattern_type not in existing_patterns:
                    events.append(e)

        # Buffer state for later ML training
        self._state_buffer.append(state)

        return events

    def extract_features(self, state: dict) -> dict:
        """
        Converts a raw traffic state dict into ML features.
        Call this to build your training dataset.
        """
        queues = state.get("queues", {})
        q_values = list(queues.values())

        total_q    = sum(q_values)
        max_q      = max(q_values) if q_values else 0
        min_q      = min(q_values) if q_values else 0
        mean_q     = np.mean(q_values) if q_values else 0
        std_q      = np.std(q_values) if q_values else 0

        # Imbalance ratio between max and min queue
        imbalance  = max_q / max(min_q, 1)

        # Phase timing features
        elapsed    = state.get("phase_duration_elapsed", 0)
        total      = state.get("phase_duration_total", 1)
        phase_pct  = elapsed / total if total > 0 else 0

        # Per-direction queues (fill 0 if direction missing)
        north = queues.get("north", 0)
        south = queues.get("south", 0)
        east  = queues.get("east",  0)
        west  = queues.get("west",  0)

        return {
            "total_queue":      total_q,
            "max_queue":        max_q,
            "min_queue":        min_q,
            "mean_queue":       mean_q,
            "std_queue":        std_q,
            "imbalance_ratio":  imbalance,
            "phase_pct_elapsed": phase_pct,
            "queue_north":      north,
            "queue_south":      south,
            "queue_east":       east,
            "queue_west":       west,
        }

    def build_training_dataframe(self, labelled_states: list[dict]) -> pd.DataFrame:
        """
        Takes a list of labelled state dicts (each has a "label" key added)
        and returns a DataFrame ready for sklearn training.

        labelled_states example:
        [
            {"junction_id": "J_001", "queues": {...}, ..., "label": "green_waste"},
            {"junction_id": "J_002", "queues": {...}, ..., "label": "normal"},
        ]
        """
        rows = []
        for state in labelled_states:
            features = self.extract_features(state)
            features["label"] = state.get("label", "normal")
            rows.append(features)
        return pd.DataFrame(rows)

    def _ml_classify(self, state: dict, existing_events: list) -> list[CongestionEvent]:
        """
        Runs the trained ML model on the current state.
        Placeholder until Week 7 when you train the model.
        """
        features  = self.extract_features(state)
        feature_df = pd.DataFrame([features])

        try:
            prediction  = self.ml_model.predict(feature_df)[0]
            probability = self.ml_model.predict_proba(feature_df).max()
        except Exception:
            return []

        if prediction == "normal" or probability < 0.6:
            return []

        return [CongestionEvent(
            junction_id    = state["junction_id"],
            pattern_type   = prediction,
            severity_score = round(float(probability), 2),
            explanation    = self._generate_ml_explanation(prediction, features, probability),
            queues         = state.get("queues", {}),
            active_phase   = state.get("active_phase", "unknown"),
        )]

    def _generate_ml_explanation(self, pattern: str, features: dict, confidence: float) -> str:
        explanations = {
            "demand_spike": (
                f"Traffic demand has spiked significantly — total queue of {features['total_queue']:.0f} "
                f"vehicles detected with high imbalance ({features['imbalance_ratio']:.1f}x). "
                f"Fixed signal timings are unable to adapt to this sudden increase. "
                f"(ML confidence: {confidence:.0%})"
            ),
            "spillback": (
                f"Queue pattern suggests spillback from an adjacent upstream junction — "
                f"one direction has an unusually large queue ({features['max_queue']:.0f} vehicles) "
                f"that cannot be attributed to local signal timing alone. "
                f"(ML confidence: {confidence:.0%})"
            ),
        }
        return explanations.get(
            pattern,
            f"ML classifier detected pattern '{pattern}' with {confidence:.0%} confidence."
        )
