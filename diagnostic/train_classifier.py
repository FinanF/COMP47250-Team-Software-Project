import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score
)

# ── 1. Load Ruhao's ground truth CSV ──────────────────────────────────────────
# Running from inside diagnostic/ folder so go up one level to find backend/
CSV_PATH = "ground_truth.csv"

print("Loading ground truth data...")
df = pd.read_csv(CSV_PATH)
print(f"Loaded {len(df)} rows")
print(f"Label distribution: {df['label'].value_counts().to_dict()}")

# ── 2. Define features — matches Ruhao's CSV column names exactly ──────────────
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

X = df[FEATURE_COLS]
y = df["label"]

print(f"\nClasses: {sorted(y.unique().tolist())}")

# ── 3. Train / test split ──────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Training on {len(X_train)} rows, testing on {len(X_test)} rows")

# ── 4. Train Random Forest ─────────────────────────────────────────────────────
print("\nTraining Random Forest classifier...")
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    random_state=42,
    class_weight="balanced"
)
model.fit(X_train, y_train)
print("Training complete.")

# ── 5. Evaluate ────────────────────────────────────────────────────────────────
y_pred = model.predict(X_test)

precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
recall    = recall_score(y_test, y_pred, average="weighted", zero_division=0)
f1        = f1_score(y_test, y_pred, average="weighted", zero_division=0)

print(f"\n{'='*50}")
print(f"  EVALUATION RESULTS")
print(f"{'='*50}")
print(f"  Precision : {precision:.4f}")
print(f"  Recall    : {recall:.4f}")
print(f"  F1 Score  : {f1:.4f}")
print(f"\nPer-class breakdown:")
print(classification_report(y_test, y_pred, zero_division=0))
print(f"\nConfusion Matrix:")
labels = sorted(y.unique())
cm     = confusion_matrix(y_test, y_pred, labels=labels)
cm_df  = pd.DataFrame(cm, index=labels, columns=labels)
print(cm_df)

# ── 6. Feature importance ──────────────────────────────────────────────────────
print(f"\nFeature Importance:")
importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
importances = importances.sort_values(ascending=False)
for feat, imp in importances.items():
    bar = "█" * int(imp * 40)
    print(f"  {feat:35s} {imp:.4f} {bar}")

# ── 7. Save model ──────────────────────────────────────────────────────────────
with open("model.pkl", "wb") as f:
    pickle.dump({
        "model":        model,
        "feature_cols": FEATURE_COLS,
        "classes":      labels
    }, f)
print(f"\nModel saved to model.pkl")

# ── 8. Save results to file ────────────────────────────────────────────────────
with open("results.txt", "w") as f:
    f.write(f"DIAGNOSTIC ALGORITHM — EVALUATION RESULTS\n")
    f.write(f"{'='*50}\n")
    f.write(f"Precision : {precision:.4f}\n")
    f.write(f"Recall    : {recall:.4f}\n")
    f.write(f"F1 Score  : {f1:.4f}\n\n")
    f.write(f"Per-class breakdown:\n")
    f.write(classification_report(y_test, y_pred, zero_division=0))
    f.write(f"\nConfusion Matrix:\n{cm_df.to_string()}\n")
    f.write(f"\nFeature Importance:\n{importances.to_string()}\n")

print("Results saved to results.txt")
print("\nDone. model.pkl is ready — DiagnosticEngine will load it automatically.")
