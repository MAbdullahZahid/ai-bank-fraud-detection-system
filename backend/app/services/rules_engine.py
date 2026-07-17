"""
Rule-based fraud checks that run ALONGSIDE the ML model's prediction.
These catch behavioral patterns the model was never trained on - PaySim has
no IP, device, timing, or account-history data, so no amount of feature
engineering on the trained model can see these. This is the standard
real-world pattern: an ML score plus a separate rules engine, combined at
decision time - not features baked into the model itself.

Each rule appends a human-readable reason if it fires. All rules are
combined with OR: any single rule firing blocks the transaction, same as
the ML model crossing its threshold.

PAYMENT and DEBIT transactions (merchants and billers) are exempt from all
rules below - counterparties for those types come from a curated, vetted
list rather than free-text phone numbers, so velocity/structuring/new-
counterparty behavior on them isn't a fraud signal, it's just someone
paying their bills. Those two types are still scored by the ML model.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.constants import CURRENCY_SYMBOL

# ---- Tunable thresholds - adjust these based on what you see in testing ----
VELOCITY_WINDOW_MINUTES = 10
VELOCITY_MAX_TRANSACTIONS = 3

NEW_COUNTERPARTY_MIN_AMOUNT = 50000

LARGE_FRACTION_OF_BALANCE = 0.9          # sending >=90% of balance in one go
BALANCE_DRAIN_MIN_AMOUNT = 20000         # ...but only counts as a signal above this {CURRENCY_SYMBOL} amount -
                                          # draining 96% of a {CURRENCY_SYMBOL} 939 balance is normal, not fraud

AMOUNT_MULTIPLIER_VS_AVERAGE = 5          # 5x this account's own average
ANOMALOUS_AMOUNT_MIN_FLOOR = 20000        # ...and only if the transaction itself clears this floor -
                                           # 5x a tiny average is still a tiny, harmless number

REPEAT_COUNTERPARTY_WINDOW_MINUTES = 15
REPEAT_COUNTERPARTY_MAX_COUNT = 2

ROUND_AMOUNT_THRESHOLD = 50000            # only check "roundness" above this size

# ATM password attempts: the frontend allows 3 total tries before locking the
# card. 2+ wrong attempts before the successful one is treated as suspicious
# (a legit customer usually gets their own password right on try 1 or 2).
FAILED_PASSWORD_ATTEMPTS_THRESHOLD = 2


def evaluate_rules(db: Session, sender, receiver, amount: float, type_: str,
                    ip_address: str = None, device: str = None,
                    failed_password_attempts: int = 0):
    """
    Runs all rules for one transaction attempt.
    `sender` is the logged-in user initiating the transaction.
    `receiver` may be None (not all scenarios have a real counterparty lookup).
    `failed_password_attempts` is the count of wrong password tries immediately
    before this attempt succeeded (ATM/CASH_OUT flow only; pass 0 elsewhere -
    it's a no-op for every other transaction type).
    Returns (any_rule_triggered: bool, reasons: list[str]).
    """
    if type_ in ("PAYMENT", "DEBIT"):
        return (False, [])

    reasons = []

    # ---- Rule 1: Velocity - too many transactions in a short window ----
    window_start = datetime.utcnow() - timedelta(minutes=VELOCITY_WINDOW_MINUTES)
    recent_count = db.query(Transaction).filter(
        Transaction.sender_id == sender.id,
        Transaction.timestamp >= window_start,
    ).count()
    if recent_count >= VELOCITY_MAX_TRANSACTIONS:
        reasons.append(
            f"Velocity rule: {recent_count} transactions from this account in the last "
            f"{VELOCITY_WINDOW_MINUTES} minutes (limit {VELOCITY_MAX_TRANSACTIONS})."
        )

    # ---- Rule 2: New/unfamiliar counterparty + large amount ----
    if receiver is not None:
        seen_before = db.query(Transaction).filter(
            Transaction.sender_id == sender.id,
            Transaction.receiver_id == receiver.id,
        ).first() is not None
        if not seen_before and amount >= NEW_COUNTERPARTY_MIN_AMOUNT:
            reasons.append(
                "New-counterparty rule: first-ever transaction to this account, "
                "combined with a large amount."
            )

    # ---- Rule 3: Large fraction of balance moved at once ----
    # Only meaningful once real money is involved - draining 96% of a {CURRENCY_SYMBOL} 939
    # balance is normal behavior for a low-balance account, not a fraud signal.
    # Both conditions must hold: the amount itself must clear a minimum floor,
    # AND it must represent a large fraction of the account's balance.
    if (
        sender.balance > 0
        and amount >= BALANCE_DRAIN_MIN_AMOUNT
        and (amount / sender.balance) >= LARGE_FRACTION_OF_BALANCE
    ):
        reasons.append(
            f"Balance-drain rule: this transaction moves "
            f"{(amount / sender.balance) * 100:.0f}% of the account's current balance "
            f"({CURRENCY_SYMBOL} {amount:,.0f})."
        )

    # ---- Rule 4: ATM password attempts - too many wrong tries before success ----
    # Only meaningful for CASH_OUT, since that's the only flow that ever passes
    # a non-zero failed_password_attempts. Every other type gets 0 -> never fires.
    if failed_password_attempts >= FAILED_PASSWORD_ATTEMPTS_THRESHOLD:
        print("[RULES] ATM-password rule triggered: "
              f"{failed_password_attempts} failed password attempts before success.")
        reasons.append(
            f"ATM-password rule: {failed_password_attempts} incorrect password attempts "
            f"were made on this account immediately before this withdrawal succeeded."
        )

    # ---- Rule 5: Amount far above this account's own typical transaction size ----
    # Only meaningful once the transaction itself is a real amount - 5x a tiny
    # average is still a tiny, harmless number.
    past_amounts = [
        t.amount for t in db.query(Transaction).filter(Transaction.sender_id == sender.id).all()
    ]
    if len(past_amounts) >= 3:
        avg_amount = sum(past_amounts) / len(past_amounts)
        if (
            avg_amount > 0
            and amount >= ANOMALOUS_AMOUNT_MIN_FLOOR
            and amount >= avg_amount * AMOUNT_MULTIPLIER_VS_AVERAGE
        ):
            reasons.append(
                f"Anomalous-amount rule: this transaction ({CURRENCY_SYMBOL} {amount:,.0f}) is over "
                f"{AMOUNT_MULTIPLIER_VS_AVERAGE}x this account's average of {CURRENCY_SYMBOL} {avg_amount:,.0f}."
            )

    # ---- Rule 6: Repeated transactions to the same counterparty in a short window ----
    if receiver is not None:
        repeat_window_start = datetime.utcnow() - timedelta(minutes=REPEAT_COUNTERPARTY_WINDOW_MINUTES)
        repeat_count = db.query(Transaction).filter(
            Transaction.sender_id == sender.id,
            Transaction.receiver_id == receiver.id,
            Transaction.timestamp >= repeat_window_start,
        ).count()
        if repeat_count >= REPEAT_COUNTERPARTY_MAX_COUNT:
            reasons.append(
                f"Repeat-counterparty rule: {repeat_count} transactions to the same "
                f"account within {REPEAT_COUNTERPARTY_WINDOW_MINUTES} minutes (possible structuring)."
            )

    # ---- Rule 7: Suspiciously round large amount ----
    if amount >= ROUND_AMOUNT_THRESHOLD and amount % 10000 == 0:
        reasons.append(
            f"Round-amount rule: {CURRENCY_SYMBOL} {amount:,.0f} is an unusually round figure for a "
            f"transaction this large."
        )

    # ---- Rule 8: New IP or device compared to this account's last transaction ----
    if ip_address and getattr(sender, "last_ip", None) and sender.last_ip != ip_address:
        reasons.append(
            "New-IP rule: this transaction came from a different IP address "
            "than this account's last known IP."
        )
    if device and getattr(sender, "last_device", None) and sender.last_device != device:
        reasons.append(
            "New-device rule: this transaction came from a different device/browser "
            "than this account's last known device."
        )

    return (len(reasons) > 0, reasons)