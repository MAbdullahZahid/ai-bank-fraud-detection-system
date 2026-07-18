"""
Rule-based fraud checks that run ALONGSIDE the ML model's prediction.
These catch behavioral patterns the model was never trained on - PaySim has
no IP, device, timing, or account-history data, so no amount of feature
engineering on the trained model can see these. This is the standard
real-world pattern: an ML score plus a separate rules engine, combined at
decision time - not features baked into the model itself.

SCORING MODEL (not plain OR):
Each rule that fires contributes a severity weight (HIGH=3, MEDIUM=2, LOW=1)
instead of blocking the transaction by itself. The transaction is only
treated as fraud if the TOTAL score across all fired rules reaches
BLOCK_SCORE_THRESHOLD. This means:
  - One HIGH-severity rule (e.g. rapid balance-drain, repeated password
    failures) blocks on its own - it's strong evidence by itself.
  - A single MEDIUM or LOW rule (e.g. a round amount, or a new device)
    does NOT block alone - those happen to innocent users constantly and
    are only meaningful combined with something else.
  - IP change is the one exception promoted to HIGH: a different IP than
    this account's last known one blocks on its own, since it's a stronger
    signal of account takeover than a device change.
  - Multiple weaker signals stacking together (e.g. new device + round amount +
    dormant account) CAN still cross the threshold and block, same as real
    fraud-scoring systems.

PAYMENT and DEBIT transactions (merchants and billers) are exempt from all
rules below - counterparties for those types come from a curated, vetted
list rather than free-text phone numbers, so velocity/structuring/new-
counterparty behavior on them isn't a fraud signal, it's just someone
paying their bills. Those two types are still scored by the ML model.

IMPORTANT - this exemption is enforced in TWO places, not one:
  1. The early return below skips scoring the CURRENT transaction if it's
     a PAYMENT or DEBIT.
  2. Every query that looks at a sender's TRANSACTION HISTORY to score a
     *different* (non-exempt) transaction also excludes PAYMENT/DEBIT rows.
     Without (2), paying a bill or a merchant would still get counted
     toward velocity/rapid-drain/fan-out/daily-limit totals for a later,
     unrelated transfer or withdrawal - which is exactly the kind of false
     positive that made the velocity and rapid-drain rules look wrong
     ("4 transactions in 10 minutes" when only some of those were actually
     transfers/withdrawals).

TIMESTAMP HANDLING:
All "within N minutes/hours/days" windows are computed in Python against a
single `now = datetime.utcnow()` captured once per evaluation, after
normalizing every timestamp to a naive UTC value. Window filtering used to
happen inside the SQL query itself (`Transaction.timestamp >= window_start`),
comparing a naive Python datetime against whatever the DB driver returns for
that column. If the column is ever timezone-aware, or a DB-side default
produced a value in a different timezone than `datetime.utcnow()`, that
comparison can silently include rows that aren't really inside the window -
which looks exactly like "the count is higher than it should be." Doing the
comparison in Python, after normalizing tzinfo away, removes that dependency
on driver/column behavior entirely.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.constants import CURRENCY_SYMBOL

# ---- Severity weights and the score needed to actually block ----
SEVERITY_HIGH = 3     # strong enough to block completely alone
SEVERITY_MEDIUM = 2   # real signal, but not alone-worthy
SEVERITY_LOW = 1      # weak signal, only meaningful combined with others
BLOCK_SCORE_THRESHOLD = 3

# Transaction types that never get scored by this engine, and whose history
# is excluded when scoring OTHER (non-exempt) transactions too. See the
# module docstring's "IMPORTANT" note above.
NON_SCORED_TYPES = ("PAYMENT", "DEBIT")

# ---- Tunable thresholds - adjust these based on what you see in testing ----
VELOCITY_WINDOW_MINUTES = 10
VELOCITY_MAX_TRANSACTIONS = 3

NEW_COUNTERPARTY_MIN_AMOUNT = 50000

LARGE_FRACTION_OF_BALANCE = 0.9
BALANCE_DRAIN_MIN_AMOUNT = 20000

AMOUNT_MULTIPLIER_VS_AVERAGE = 5
ANOMALOUS_AMOUNT_MIN_FLOOR = 20000

REPEAT_COUNTERPARTY_WINDOW_MINUTES = 15
REPEAT_COUNTERPARTY_MAX_COUNT = 2

ROUND_AMOUNT_THRESHOLD = 50000

# ATM password attempts: the frontend allows 3 total tries before locking the
# card. 2+ wrong attempts before the successful one is treated as suspicious.
FAILED_PASSWORD_ATTEMPTS_THRESHOLD = 2

RAPID_DRAIN_WINDOW_MINUTES = 10
RAPID_DRAIN_FRACTION = 0.9
RAPID_DRAIN_MIN_TOTAL = 20000

FAN_OUT_WINDOW_MINUTES = 20
FAN_OUT_MIN_DISTINCT_RECEIVERS = 4

DORMANT_DAYS_THRESHOLD = 90
DORMANT_MIN_AMOUNT = 20000

NEW_ACCOUNT_MAX_TX_COUNT = 5
NEW_ACCOUNT_MAX_AGE_DAYS = 30
NEW_ACCOUNT_MIN_AMOUNT = 50000

SPIKE_MULTIPLIER_VS_PREVIOUS = 20
SPIKE_MIN_AMOUNT = 20000

RECENT_FRAUD_WINDOW_HOURS = 1
RECENT_FRAUD_MAX_COUNT = 3

DAILY_SPEND_LIMIT = 200000

# Receiver lock: same rolling-window "lock" pattern as the ATM card lock
# below, but on the receiving side. 3+ fraud-flagged transactions TO this
# receiver (any transaction type, any sender) within a 2-day window reads as
# "this account is temporarily locked from receiving". Rolling window, not a
# stored lock timestamp - self-clears once old fraud incidents age out past
# RECEIVER_LOCK_WINDOW_DAYS and the count drops back under the threshold.
RECEIVER_LOCK_FRAUD_COUNT_THRESHOLD = 3
RECEIVER_LOCK_WINDOW_DAYS = 2


def _as_naive_utc(dt):
    """Normalize a timestamp to a naive datetime so every window comparison
    in this module is done the same way, regardless of whether the DB
    driver handed back a naive or timezone-aware value."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def evaluate_rules(db: Session, sender, receiver, amount: float, type_: str,
                    ip_address: str = None, device: str = None,
                    failed_password_attempts: int = 0):
    """
    Runs all rules for one transaction attempt and scores them.
    Returns (any_rule_triggered: bool, reasons: list[str]) - same signature
    as before, but "triggered" now means the combined severity score reached
    BLOCK_SCORE_THRESHOLD, not just "at least one rule fired".
    """
    if type_ in NON_SCORED_TYPES:
        return (False, [])

    fired = []  # list of (severity_weight, reason_text)
    now = datetime.utcnow()

    # ---- Single fetch of this sender's history, reused by every rule below.
    # Excludes PAYMENT/DEBIT rows so routine bill payments and merchant
    # checkouts never inflate the score of an unrelated transfer/withdrawal.
    # All time-window filtering happens here in Python (see module docstring)
    # instead of inside the SQL query.
    all_sender_tx = db.query(Transaction).filter(Transaction.sender_id == sender.id).all()
    scored_sender_tx = [t for t in all_sender_tx if t.type not in NON_SCORED_TYPES]

    # ---- Rule 1 [MEDIUM]: Velocity - too many transactions in a short window ----
    velocity_window_start = now - timedelta(minutes=VELOCITY_WINDOW_MINUTES)
    recent_count = sum(
        1 for t in scored_sender_tx
        if _as_naive_utc(t.timestamp) and _as_naive_utc(t.timestamp) >= velocity_window_start
    )
    if recent_count >= VELOCITY_MAX_TRANSACTIONS:
        fired.append((SEVERITY_MEDIUM,
            f"Velocity rule: {recent_count} transactions from this account in the last "
            f"{VELOCITY_WINDOW_MINUTES} minutes (limit {VELOCITY_MAX_TRANSACTIONS})."
        ))

    # ---- Rule 2 [MEDIUM]: New/unfamiliar counterparty + large amount ----
    if receiver is not None:
        seen_before = db.query(Transaction).filter(
            Transaction.sender_id == sender.id,
            Transaction.receiver_id == receiver.id,
        ).first() is not None
        if not seen_before and amount >= NEW_COUNTERPARTY_MIN_AMOUNT:
            fired.append((SEVERITY_MEDIUM,
                "New-counterparty rule: first-ever transaction to this account, "
                "combined with a large amount."
            ))

    # ---- Rule 3 [HIGH]: Large fraction of balance moved at once ----
    if (
        sender.balance > 0
        and amount >= BALANCE_DRAIN_MIN_AMOUNT
        and (amount / sender.balance) >= LARGE_FRACTION_OF_BALANCE
    ):
        fired.append((SEVERITY_HIGH,
            f"Balance-drain rule: this transaction moves "
            f"{(amount / sender.balance) * 100:.0f}% of the account's current balance "
            f"({CURRENCY_SYMBOL} {amount:,.0f})."
        ))

    # ---- Rule 4 [HIGH]: ATM password attempts - too many wrong tries before success ----
    if failed_password_attempts >= FAILED_PASSWORD_ATTEMPTS_THRESHOLD:
        print("[RULES] ATM-password rule triggered: "
              f"{failed_password_attempts} failed password attempts before success.")
        fired.append((SEVERITY_HIGH,
            f"ATM-password rule: {failed_password_attempts} incorrect password attempts "
            f"were made on this account immediately before this withdrawal succeeded."
        ))

    # ---- Rule 5 [MEDIUM]: Amount far above this account's own typical size ----
    past_amounts = [t.amount for t in scored_sender_tx]
    if len(past_amounts) >= 3:
        avg_amount = sum(past_amounts) / len(past_amounts)
        if (
            avg_amount > 0
            and amount >= ANOMALOUS_AMOUNT_MIN_FLOOR
            and amount >= avg_amount * AMOUNT_MULTIPLIER_VS_AVERAGE
        ):
            fired.append((SEVERITY_MEDIUM,
                f"Anomalous-amount rule: this transaction ({CURRENCY_SYMBOL} {amount:,.0f}) is over "
                f"{AMOUNT_MULTIPLIER_VS_AVERAGE}x this account's average of {CURRENCY_SYMBOL} {avg_amount:,.0f}."
            ))

    # ---- Rule 6 [MEDIUM]: Repeated transactions to the same counterparty ----
    if receiver is not None:
        repeat_window_start = now - timedelta(minutes=REPEAT_COUNTERPARTY_WINDOW_MINUTES)
        repeat_count = sum(
            1 for t in scored_sender_tx
            if t.receiver_id == receiver.id
            and _as_naive_utc(t.timestamp)
            and _as_naive_utc(t.timestamp) >= repeat_window_start
        )
        if repeat_count >= REPEAT_COUNTERPARTY_MAX_COUNT:
            fired.append((SEVERITY_MEDIUM,
                f"Repeat-counterparty rule: {repeat_count} transactions to the same "
                f"account within {REPEAT_COUNTERPARTY_WINDOW_MINUTES} minutes (possible structuring)."
            ))

    # ---- Rule 7 [LOW]: Suspiciously round large amount ----
    if amount >= ROUND_AMOUNT_THRESHOLD and amount % 10000 == 0:
        fired.append((SEVERITY_LOW,
            f"Round-amount rule: {CURRENCY_SYMBOL} {amount:,.0f} is an unusually round figure for a "
            f"transaction this large."
        ))

    # ---- Rule 8a [HIGH]: New IP compared to this account's last transaction ----
    # IP change blocks ALONE - session hijacking / credential theft is typically
    # used from a different network than the real account owner's. Only fires
    # once last_ip is already on record (never on a user's very first transaction).
    if ip_address and getattr(sender, "last_ip", None) and sender.last_ip != ip_address:
        fired.append((SEVERITY_HIGH,
            "New-IP rule: this transaction came from a different IP address "
            "than this account's last known IP."
        ))

    # ---- Rule 8b [LOW]: New device compared to this account's last transaction ----
    # Stays weak alone - switching phones/browsers is common and usually innocent,
    # unlike an IP change. Only meaningful combined with another signal.
    if device and getattr(sender, "last_device", None) and sender.last_device != device:
        fired.append((SEVERITY_LOW,
            "New-device rule: this transaction came from a different device/browser "
            "than this account's last known device."
        ))

    # ---- Rule 9 [HIGH]: Rapid balance depletion across multiple transactions ----
    drain_window_start = now - timedelta(minutes=RAPID_DRAIN_WINDOW_MINUTES)
    total_sent_recently = sum(
        t.amount for t in scored_sender_tx
        if _as_naive_utc(t.timestamp) and _as_naive_utc(t.timestamp) >= drain_window_start
    ) + amount
    if (
        sender.balance > 0
        and total_sent_recently >= RAPID_DRAIN_MIN_TOTAL
        and total_sent_recently >= sender.balance * RAPID_DRAIN_FRACTION
    ):
        fired.append((SEVERITY_HIGH,
            f"Rapid balance-drain rule: {CURRENCY_SYMBOL} {total_sent_recently:,.0f} sent across "
            f"multiple transactions in the last {RAPID_DRAIN_WINDOW_MINUTES} minutes - "
            f"nearly the entire account balance."
        ))

    # ---- Rule 10 [HIGH]: Recipient diversity (fan-out) ----
    fan_out_window_start = now - timedelta(minutes=FAN_OUT_WINDOW_MINUTES)
    recent_receiver_count = len({
        t.receiver_id for t in scored_sender_tx
        if _as_naive_utc(t.timestamp) and _as_naive_utc(t.timestamp) >= fan_out_window_start
    })
    if recent_receiver_count >= FAN_OUT_MIN_DISTINCT_RECEIVERS:
        fired.append((SEVERITY_HIGH,
            f"Recipient-diversity rule: transfers sent to {recent_receiver_count} different "
            f"recipients within {FAN_OUT_WINDOW_MINUTES} minutes."
        ))

    # ---- Rule 11 [MEDIUM]: Dormant account suddenly reactivated ----
    # "Last transaction" here means the last SCORED (non-exempt) transaction -
    # paying a routine bill doesn't count as the account "waking up" for the
    # purposes of a transfer or withdrawal.
    last_tx = max(scored_sender_tx, key=lambda t: t.timestamp) if scored_sender_tx else None
    if last_tx and last_tx.timestamp:
        idle_days = (now - _as_naive_utc(last_tx.timestamp)).days
        if idle_days >= DORMANT_DAYS_THRESHOLD and amount >= DORMANT_MIN_AMOUNT:
            fired.append((SEVERITY_MEDIUM,
                f"Dormant-account rule: first transaction after {idle_days} days of "
                f"inactivity, for {CURRENCY_SYMBOL} {amount:,.0f}."
            ))

    # ---- Rule 12 [MEDIUM]: Large transfer from a new/young account ----
    past_tx_count = len(past_amounts)
    account_age_days = (
        (now - _as_naive_utc(sender.created_at)).days
        if getattr(sender, "created_at", None) else None
    )
    if (
        past_tx_count < NEW_ACCOUNT_MAX_TX_COUNT
        and account_age_days is not None
        and account_age_days <= NEW_ACCOUNT_MAX_AGE_DAYS
        and amount >= NEW_ACCOUNT_MIN_AMOUNT
    ):
        fired.append((SEVERITY_MEDIUM,
            f"New-account rule: account is {account_age_days} days old with only "
            f"{past_tx_count} prior transactions, now sending {CURRENCY_SYMBOL} {amount:,.0f}."
        ))

    # ---- Rule 13 [MEDIUM]: Sudden spike vs. the immediately previous transaction ----
    if last_tx and amount >= SPIKE_MIN_AMOUNT and last_tx.amount > 0:
        if amount >= last_tx.amount * SPIKE_MULTIPLIER_VS_PREVIOUS:
            fired.append((SEVERITY_MEDIUM,
                f"Transaction-spike rule: {CURRENCY_SYMBOL} {amount:,.0f} is over "
                f"{SPIKE_MULTIPLIER_VS_PREVIOUS}x this account's previous transaction of "
                f"{CURRENCY_SYMBOL} {last_tx.amount:,.0f}."
            ))

    # ---- Rule 14 [HIGH]: Multiple recent fraud blocks from this sender ----
    # Uses ALL transaction types (not just scored_sender_tx) - a fraud flag on
    # a merchant payment, driven by the ML model, is still a real signal about
    # this account's recent behavior.
    fraud_window_start = now - timedelta(hours=RECENT_FRAUD_WINDOW_HOURS)
    recent_fraud_count = sum(
        1 for t in all_sender_tx
        if t.prediction == "fraud"
        and _as_naive_utc(t.timestamp)
        and _as_naive_utc(t.timestamp) >= fraud_window_start
    )
    if recent_fraud_count >= RECENT_FRAUD_MAX_COUNT:
        fired.append((SEVERITY_HIGH,
            f"Repeated-fraud rule: {recent_fraud_count} transactions from this account were "
            f"already blocked in the last {RECENT_FRAUD_WINDOW_HOURS} hour(s)."
        ))

    # ---- Rule 15 [MEDIUM]: High total spending today ----
    today_start = datetime.combine(now.date(), datetime.min.time())
    daily_total = sum(
        t.amount for t in scored_sender_tx
        if _as_naive_utc(t.timestamp) and _as_naive_utc(t.timestamp) >= today_start
    ) + amount
    if daily_total >= DAILY_SPEND_LIMIT:
        fired.append((SEVERITY_MEDIUM,
            f"Daily-limit rule: {CURRENCY_SYMBOL} {daily_total:,.0f} sent today across all "
            f"transactions, exceeding the normal daily threshold."
        ))

    # ---- Rule 16 [HIGH]: Receiver lock - repeated recent fraud landing on this account ----
    # Mirrors the ATM card-lock rule (4), but for the receiving side: 3+
    # fraud-flagged transactions TO this receiver, of ANY transaction type,
    # from any sender, within a 2-day rolling window - blocks alone, like a
    # temporary receive-side freeze. Self-clears as old incidents age past
    # RECEIVER_LOCK_WINDOW_DAYS and the count drops back under the threshold.
    if receiver is not None:
        receiver_lock_window_start = now - timedelta(days=RECEIVER_LOCK_WINDOW_DAYS)
        receiver_tx = db.query(Transaction).filter(Transaction.receiver_id == receiver.id).all()
        receiver_fraud_count = sum(
            1 for t in receiver_tx
            if t.prediction == "fraud"
            and _as_naive_utc(t.timestamp)
            and _as_naive_utc(t.timestamp) >= receiver_lock_window_start
        )
        if receiver_fraud_count >= RECEIVER_LOCK_FRAUD_COUNT_THRESHOLD:
            fired.append((SEVERITY_HIGH,
                f"Receiver-lock rule: {receiver_fraud_count} fraudulent transactions landed on "
                f"this recipient in the last {RECEIVER_LOCK_WINDOW_DAYS} days - "
                f"recipient temporarily locked."
            ))

    # ---- Score everything that fired ----
    total_score = sum(weight for weight, _ in fired)
    reasons = [text for _, text in fired]
    triggered = total_score >= BLOCK_SCORE_THRESHOLD

    if fired:
        print(f"[RULES] {len(fired)} rule(s) fired, total score={total_score} "
              f"(threshold={BLOCK_SCORE_THRESHOLD}) -> {'BLOCKED' if triggered else 'allowed (below threshold)'}")

    return (triggered, reasons if triggered else [])