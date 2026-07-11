"""
engine.py — DiagnosticEngine
Combines Layer 1 (rule-based) and Layer 2 (ML classifier).
Pure Python — no asyncio here. The worker wraps this.
"""

import pickle
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from diagnostic.rules import RuleBasedDetector


@dataclass
class CongestionEvent:
    junction_id:    str
    pattern_type:   str
    severity_score: float
    explanation:    str
    queues:         dict
    active_phase:   str
    detected_at:    str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MLClassifier:
    """Loads model.pkl and classifies incoming states."""

    FEATURE_COLS = [
        "current_phase",
        "phase_duration_total",
        "phase_duration_remaining",
        "max_queue_length",
        "avg_queue_length",
        "max_waiting_time",
        "green_lane_count",
        "empty_green_lane_count",
        "max_seconds_since_green",
        "approach_count",
    ]

    def __init__(self, model_path: str = "model.pkl"):
        try:
            with open(model_path, "rb") as f:
                data = pickle.load(f)
            self.model   = data["model"]
            self.classes = data["classes"]
            self.ready   = True
            print(f"[MLClassifier] Loaded model from {model_path}")
        except FileNotFoundError:
            self.ready = False
            print(f"[MLClassifier] model.pkl not found — run train_classifier.py first")

    def predict(self, state: dict):
        """
        Returns (pattern_type, confidence) or (None, 0) if below threshold.
        """
        if not self.ready:
            return None, 0.0

        features = {
            "current_phase":            state.get("current_phase", 0),
            "phase_duration_total":     state.get("phase_duration_total", 0),
            "phase_duration_remaining": state.get("phase_duration_remaining", 0),
            "max_queue_length":         state.get("max_queue_length", 0),
            "avg_queue_length":         state.get("avg_queue_length", 0.0),
            "max_waiting_time":         state.get("max_waiting_time", 0.0),
            "green_lane_count":         state.get("green_lane_count", 0),
            "empty_green_lane_count":   state.get("empty_green_lane_count", 0),
            "max_seconds_since_green":  state.get("max_seconds_since_green", 0.0),
            "approach_count":           state.get("approach_count", 0),
        }

        df          = pd.DataFrame([features])[self.FEATURE_COLS]
        prediction  = self.model.predict(df)[0]
        confidence  = self.model.predict_proba(df).max()
        if prediction == "normal" or confidence < 0.6:
            return None, 0.0

        return prediction, float(confidence)


class DiagnosticEngine:
    """
    Main engine. Call analyse(state) on every incoming traffic state.
    Layer 1 — RuleBasedDetector : fast, always runs, no training needed
    Layer 2 — MLClassifier      : catches subtler patterns, needs model.pkl
    """

    def __init__(self, model_path: str = "model.pkl"):
        self.rule_detector = RuleBasedDetector()
        self.ml_classifier = MLClassifier(model_path)

    def analyse(self, state: dict) -> list:
        events = []

        # Layer 1 — always runs
        rule_events = self.rule_detector.analyse(state)
        events.extend(rule_events)

        # Layer 2 — only runs if model.pkl exists
        if self.ml_classifier.ready:
            pattern, confidence = self.ml_classifier.predict(state)
            if pattern is not None:
                print(f"[DiagnosticEngine] ML prediction: {pattern} (confidence {confidence:.0%})")
            existing = {e.pattern_type for e in rule_events}
            if pattern and pattern not in existing:
                events.append(CongestionEvent(
                    junction_id    = str(state.get("junction_id", "unknown")),
                    pattern_type   = pattern,
                    severity_score = round(confidence, 2),
                    explanation    = self._explain(pattern, confidence, state),
                    queues         = state.get("queues", {}),
                    active_phase   = str(state.get("current_phase", "unknown")),
                ))
                print(f"[DiagnosticEngine] ML detected {pattern} at junction {state.get('junction_id')} (confidence {confidence:.0%})")
        return events

    def _explain(self, pattern: str, confidence: float, state: dict) -> str:
        explanations = {
            "starvation": (
                f"Junction {state.get('junction_id')} has a maximum queue of "
                f"{state.get('max_queue_length', 0)} vehicles with "
                f"{state.get('max_seconds_since_green', 0):.0f}s since last green. "
                f"One or more approaches are not receiving sufficient green time. "
                f"(ML confidence: {confidence:.0%})"
            ),
            "green_waste": (
                f"{state.get('empty_green_lane_count', 0)} of "
                f"{state.get('green_lane_count', 0)} green lanes are empty at junction "
                f"{state.get('junction_id')} while other approaches queue. "
                f"Signal time is being wasted. "
                f"(ML confidence: {confidence:.0%})"
            ),
            "demand_imbalance": (
                f"Junction {state.get('junction_id')} has an uneven demand distribution "
                f"across {state.get('approach_count', 0)} approaches — max queue "
                f"{state.get('max_queue_length', 0)}, avg {state.get('avg_queue_length', 0):.1f}. "
                f"Phase timing does not match actual demand. "
                f"(ML confidence: {confidence:.0%})"
            ),
        }
        return explanations.get(
            pattern,
            f"ML classifier detected '{pattern}' at junction "
            f"{state.get('junction_id')} with {confidence:.0%} confidence."
        )
