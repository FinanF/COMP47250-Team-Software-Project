import pickle
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
try:
    from diagnostic.rules import RuleBasedDetector
except ImportError:
    from rules import RuleBasedDetector


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

    def _extract_features(self, state: dict) -> dict:
        approaches  = state.get("approaches", [])
        queues      = [a.get("queue_length", 0) for a in approaches]
        max_q       = max(queues) if queues else 0
        avg_q       = sum(queues) / len(queues) if queues else 0.0
        max_wait    = max((a.get("waiting_time_avg", 0) for a in approaches), default=0)
        green_lanes = [a for a in approaches if a.get("green") is True]
        empty_green = sum(1 for a in green_lanes if a.get("queue_length", 0) == 0)
        max_ssg     = max((a.get("seconds_since_green") or 0 for a in approaches), default=0)

        return {
            "current_phase":            state.get("current_phase", 0),
            "phase_duration_total":     state.get("phase_duration_total", 0),
            "phase_duration_remaining": state.get("phase_duration_remaining", 0),
            "max_queue_length":         max_q,
            "avg_queue_length":         avg_q,
            "max_waiting_time":         max_wait,
            "green_lane_count":         len(green_lanes),
            "empty_green_lane_count":   empty_green,
            "max_seconds_since_green":  max_ssg,
            "approach_count":           len(approaches),
        }

    def predict(self, state: dict):
        if not self.ready:
            return None, 0.0

        try:
            features   = self._extract_features(state)
            df         = pd.DataFrame([features])[self.FEATURE_COLS]
            prediction = self.model.predict(df)[0]
            confidence = self.model.predict_proba(df).max()
        except Exception as e:
            print(f"[MLClassifier] Prediction error: {e}")
            return None, 0.0

        if prediction == "normal" or confidence < 0.6:
            return None, 0.0

        return prediction, float(confidence)


class DiagnosticEngine:

    def __init__(self, model_path: str = "model.pkl"):
        self.rule_detector = RuleBasedDetector()
        self.ml_classifier = MLClassifier(model_path)

    def analyse(self, state: dict) -> list:
        events = []

        rule_events = self.rule_detector.analyse(state)
        events.extend(rule_events)

        if self.ml_classifier.ready:
            pattern, confidence = self.ml_classifier.predict(state)
            existing = {e.pattern_type for e in rule_events}

            if pattern and pattern not in existing:
                approaches = state.get("approaches", [])
                queues_snapshot = {
                    a.get("lane_id", "unknown"): a.get("queue_length", 0)
                    for a in approaches
                }
                events.append(CongestionEvent(
                    junction_id    = str(state.get("id", state.get("junction_id", "unknown"))),
                    pattern_type   = pattern,
                    severity_score = round(confidence, 2),
                    explanation    = self._explain(pattern, confidence, state),
                    queues         = queues_snapshot,
                    active_phase   = str(state.get("current_phase", "unknown")),
                ))

        return events

    def _explain(self, pattern: str, confidence: float, state: dict) -> str:
        approaches  = state.get("approaches", [])
        queues      = [a.get("queue_length", 0) for a in approaches]
        max_q       = max(queues) if queues else 0
        avg_q       = sum(queues) / len(queues) if queues else 0.0
        green_lanes = [a for a in approaches if a.get("green") is True]
        empty_green = sum(1 for a in green_lanes if a.get("queue_length", 0) == 0)
        max_ssg     = max((a.get("seconds_since_green", 0) for a in approaches), default=0)
        jid         = state.get("id", state.get("junction_id", "unknown"))

        explanations = {
            "starvation": (
                f"Junction {jid} has a maximum queue of {max_q} vehicles "
                f"with {max_ssg:.0f}s since last green. "
                f"One or more approaches are not receiving sufficient green time. "
                f"(ML confidence: {confidence:.0%})"
            ),
            "green_waste": (
                f"{empty_green} of {len(green_lanes)} green lanes are empty "
                f"at junction {jid} while other approaches queue. "
                f"Signal time is being wasted. "
                f"(ML confidence: {confidence:.0%})"
            ),
            "demand_imbalance": (
                f"Junction {jid} has an uneven demand distribution "
                f"across {len(approaches)} approaches — max queue {max_q}, "
                f"avg {avg_q:.1f}. Phase timing does not match actual demand. "
                f"(ML confidence: {confidence:.0%})"
            ),
        }
        return explanations.get(
            pattern,
            f"ML classifier detected '{pattern}' at junction {jid} "
            f"with {confidence:.0%} confidence."
        )
