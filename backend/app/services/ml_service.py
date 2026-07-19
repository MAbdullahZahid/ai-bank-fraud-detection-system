import os
from datetime import datetime
import joblib
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = os.getenv("MODEL_PATH", "../ml/models/xgboost_model.joblib")
THRESHOLD = float(os.getenv("THRESHOLD", 0.5))

MODELS_DIR = os.path.dirname(MODEL_PATH)
ENCODER_PATH = os.path.join(MODELS_DIR, "label_encoder.joblib")
SCALER_PATH = os.path.join(MODELS_DIR, "scaler.joblib")

# Loaded once, reused across all requests (do not reload per-request - slow)
model = joblib.load(MODEL_PATH)
label_encoder = joblib.load(ENCODER_PATH)
scaler = joblib.load(SCALER_PATH)

# Must match the exact column order used in training (X_train.columns)
FEATURE_ORDER = [
    "step", "type", "amount", "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest", "isFlaggedFraud", "isMerchant",
    "balanceOrigDiff", "balanceDestDiff", "errorBalanceOrig", "errorBalanceDest",
]

# Only these columns were fit into the StandardScaler during training
NUMERIC_COLS_TO_SCALE = [
    "amount", "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest",
    "balanceOrigDiff", "balanceDestDiff",
    "errorBalanceOrig", "errorBalanceDest",
]

# Arbitrary reference point so "step" mirrors PaySim's hourly simulation clock.
# step's feature importance was low in training, so this is a reasonable stand-in
# for real elapsed time without needing to replicate the original 30-day simulation.
_SIMULATION_START = datetime(2026, 1, 1)


def _current_step() -> int:
    hours_elapsed = int((datetime.utcnow() - _SIMULATION_START).total_seconds() // 3600)
    return (hours_elapsed % 743) + 1  # PaySim's step range is 1-743


def build_feature_row(
    type_: str,
    amount: float,
    old_balance_orig: float,
    new_balance_orig: float,
    old_balance_dest: float,
    new_balance_dest: float,
    is_merchant: int = 0,
) -> pd.DataFrame:
    # Replicates PaySim's own flagged-fraud rule (amount > 200,000 on a TRANSFER)
    is_flagged_fraud = 1 if (type_ == "TRANSFER" and amount > 200000) else 0

    balance_orig_diff = old_balance_orig - new_balance_orig
    balance_dest_diff = new_balance_dest - old_balance_dest
    error_balance_orig = old_balance_orig - amount - new_balance_orig
    error_balance_dest = old_balance_dest + amount - new_balance_dest

    type_encoded = int(label_encoder.transform([type_])[0])

    row = {
        "step": _current_step(),
        "type": type_encoded,
        "amount": amount,
        "oldbalanceOrg": old_balance_orig,
        "newbalanceOrig": new_balance_orig,
        "oldbalanceDest": old_balance_dest,
        "newbalanceDest": new_balance_dest,
        "isFlaggedFraud": is_flagged_fraud,
        "isMerchant": is_merchant,
        "balanceOrigDiff": balance_orig_diff,
        "balanceDestDiff": balance_dest_diff,
        "errorBalanceOrig": error_balance_orig,
        "errorBalanceDest": error_balance_dest,
    }

    df = pd.DataFrame([row])[FEATURE_ORDER]
    df[NUMERIC_COLS_TO_SCALE] = scaler.transform(df[NUMERIC_COLS_TO_SCALE])
    return df


def predict_fraud(
    type_: str,
    amount: float,
    old_balance_orig: float,
    new_balance_orig: float,
    old_balance_dest: float,
    new_balance_dest: float,
    is_merchant: int = 0,
) -> tuple[float, bool]:
    features = build_feature_row(
        type_, amount, old_balance_orig, new_balance_orig,
        old_balance_dest, new_balance_dest, is_merchant,
    )
    probability = float(model.predict_proba(features)[0, 1])
    is_fraud = probability >= THRESHOLD
    return probability, is_fraud
