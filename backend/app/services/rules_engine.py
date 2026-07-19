from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.constants import CURRENCY_SYMBOL

# ---- Severity weights and the score needed to actually block ----
SEVERITY_HIGH = 3
SEVERITY_MEDIUM = 2
SEVERITY_LOW = 1
BLOCK_SCORE_THRESHOLD = 3

# Behavioral rules don't apply to these types - Rule 0 (the model) still does.
NON_SCORED_TYPES = ("PAYMENT", "DEBIT","CASH_IN")

# ---- Rule 0: the ML model's own probability, converted into severity ----
# NOTE: since this file now owns the fraud/legit decision entirely, the old
# separate `THRESHOLD` check in transactions.py (`is_fraud = probability >=
# THRESHOLD`) should be REMOVED - it would otherwise silently duplicate/
# conflict with this. See the integration note at the bottom of this file.
MODEL_HIGH_PROBABILITY = 0.70
MODEL_MEDIUM_PROBABILITY = 0.40
MODEL_LOW_PROBABILITY = 0.15

# ---- Account-scale calculation ----
ACCOUNT_SCALE_FLOOR = 5000


def _account_scale(sender_balance: float, legit_avg_amount: float) -> float:
    return max(sender_balance or 0, legit_avg_amount or 0, ACCOUNT_SCALE_FLOOR)


def _scaled_threshold(scale: float, fraction: float, absolute_floor: float) -> float:
    return max(absolute_floor, scale * fraction)


# ---- Tunable thresholds ----
VELOCITY_WINDOW_MINUTES = 10
VELOCITY_MAX_TRANSACTIONS = 3

NEW_COUNTERPARTY_MIN_FRACTION = 0.15
NEW_COUNTERPARTY_ABS_FLOOR = 20000

LARGE_FRACTION_OF_BALANCE = 0.9           # rule 3 default fraction - now only a fallback, see helper below
BALANCE_DRAIN_MIN_AMOUNT = 200000          # fixed floor - filters trivial balances only

# Rule 3's fraction threshold now scales with balance instead of being flat:
#   - Small balances: near-total drains are ordinary (someone spending down
#     most of a ₨50,000 balance isn't suspicious) - so allow a HIGHER % before flagging.
#   - Large balances: even a smaller % is a huge absolute sum - so flag at a LOWER %.
# Between the two cutoffs, the threshold interpolates linearly.
BALANCE_DRAIN_LOW_BALANCE_CUTOFF = 100000       # at/below this balance -> lenient threshold
BALANCE_DRAIN_HIGH_BALANCE_CUTOFF = 5000000     # at/above this balance -> strict threshold
BALANCE_DRAIN_FRACTION_FOR_LOW_BALANCE = 0.95   # e.g. ₨50,000 balance: only flag above 95% moved
BALANCE_DRAIN_FRACTION_FOR_HIGH_BALANCE = 0.50  # e.g. ₨2-crore balance: flag once 50%+ moved


def _balance_drain_fraction_threshold(balance: float) -> float:
    if balance <= BALANCE_DRAIN_LOW_BALANCE_CUTOFF:
        return BALANCE_DRAIN_FRACTION_FOR_LOW_BALANCE
    if balance >= BALANCE_DRAIN_HIGH_BALANCE_CUTOFF:
        return BALANCE_DRAIN_FRACTION_FOR_HIGH_BALANCE
    span = BALANCE_DRAIN_HIGH_BALANCE_CUTOFF - BALANCE_DRAIN_LOW_BALANCE_CUTOFF
    position = (balance - BALANCE_DRAIN_LOW_BALANCE_CUTOFF) / span
    return BALANCE_DRAIN_FRACTION_FOR_LOW_BALANCE + position * (
        BALANCE_DRAIN_FRACTION_FOR_HIGH_BALANCE - BALANCE_DRAIN_FRACTION_FOR_LOW_BALANCE
    )

AMOUNT_MULTIPLIER_VS_AVERAGE = 5           # rule 5 - already relative to this account's own average
ANOMALOUS_AMOUNT_MIN_FLOOR = 20000         # fixed floor - filters trivial averages only

REPEAT_COUNTERPARTY_WINDOW_MINUTES = 15
REPEAT_COUNTERPARTY_MAX_COUNT = 2

ROUND_AMOUNT_FRACTION = 0.15
ROUND_AMOUNT_ABS_FLOOR = 20000

FAILED_PASSWORD_ATTEMPTS_THRESHOLD = 2

RAPID_DRAIN_WINDOW_MINUTES = 10
# Fraction threshold now comes from the same balance-tiered helper as rule 3
# (_balance_drain_fraction_threshold) - lenient for small balances, strict
# for large ones. No separate flat constant needed here anymore.
RAPID_DRAIN_MIN_TOTAL = 20000              # fixed floor - filters trivial balances only

FAN_OUT_WINDOW_MINUTES = 20
FAN_OUT_MIN_DISTINCT_RECEIVERS = 4

DORMANT_DAYS_THRESHOLD = 90
DORMANT_MIN_FRACTION = 0.10
DORMANT_ABS_FLOOR = 15000

NEW_ACCOUNT_MAX_TX_COUNT = 5
NEW_ACCOUNT_MAX_AGE_DAYS = 30
NEW_ACCOUNT_MIN_FRACTION = 0.15
NEW_ACCOUNT_ABS_FLOOR = 20000

SPIKE_MULTIPLIER_VS_PREVIOUS = 20
SPIKE_MIN_FRACTION = 0.10
SPIKE_ABS_FLOOR = 15000

RECENT_FRAUD_WINDOW_HOURS = 1
RECENT_FRAUD_MAX_COUNT = 3

DAILY_SPEND_FRACTION = 0.5
DAILY_SPEND_ABS_FLOOR = 1000000

RECEIVER_LOCK_FRAUD_COUNT_THRESHOLD = 3
RECEIVER_LOCK_WINDOW_DAYS = 2


def _as_naive_utc(dt):
    """Normalize a timestamp to a naive UTC datetime so every window
    comparison in this module is done on the same clock."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def evaluate_rules(db: Session, sender, receiver, amount: float, type_: str,
                    probability: float = 0.0,
                    ip_address: str = None, device: str = None,
                    failed_password_attempts: int = 0):
    """
    Scores the ML model's probability (Rule 0) alongside every behavioral
    rule, in one combined total. `probability` is the model's fraud
    probability for THIS transaction - pass it in from wherever
    predict_fraud() is called.

    Returns (any_rule_triggered: bool, reasons: list[str]).
    """
    fired = []
    now = datetime.utcnow()

    # ---- Rule 0 [scored by probability]: the ML model's own prediction ----
    if probability >= MODEL_HIGH_PROBABILITY:
        fired.append((SEVERITY_HIGH,
            f"ML model rule: fraud probability {probability:.4f} "
            f"(>= {MODEL_HIGH_PROBABILITY} high-confidence threshold)."
        ))
    elif probability >= MODEL_MEDIUM_PROBABILITY:
        fired.append((SEVERITY_MEDIUM,
            f"ML model rule: fraud probability {probability:.4f} "
            f"(>= {MODEL_MEDIUM_PROBABILITY} medium-confidence threshold)."
        ))
    elif probability >= MODEL_LOW_PROBABILITY:
        fired.append((SEVERITY_LOW,
            f"ML model rule: fraud probability {probability:.4f} "
            f"(>= {MODEL_LOW_PROBABILITY} low-confidence threshold)."
        ))
    print(f"[RULES] ML model probability for this transaction: {probability:.4f}")

    if type_ in NON_SCORED_TYPES:
        total_score = sum(weight for weight, _ in fired)
        reasons = [text for _, text in fired]
        triggered = total_score >= BLOCK_SCORE_THRESHOLD
        if fired:
            print(f"[RULES] (PAYMENT/DEBIT - only Rule 0 applies) score={total_score} "
                  f"(threshold={BLOCK_SCORE_THRESHOLD}) -> {'BLOCKED' if triggered else 'allowed'}")
        return (triggered, reasons if triggered else [])

    all_sender_tx = db.query(Transaction).filter(Transaction.sender_id == sender.id).all()
    scored_sender_tx = [t for t in all_sender_tx if t.type not in NON_SCORED_TYPES]

    # Legit-only subset - a blocked transaction never actually moved money.
    legit_scored_tx = [t for t in scored_sender_tx if t.prediction == "legit"]
    past_amounts_legit = [t.amount for t in legit_scored_tx]
    avg_legit_amount = sum(past_amounts_legit) / len(past_amounts_legit) if past_amounts_legit else 0

    # All attempts (including blocked) - used for attempt-pattern signals.
    past_amounts_all = [t.amount for t in scored_sender_tx]

    account_scale = _account_scale(sender.balance, avg_legit_amount)

    # ---- Rule 1 [MEDIUM]: Velocity ----
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

    # ---- Rule 2 [MEDIUM]: New counterparty + large amount (scaled) ----
    if receiver is not None:
        seen_before = db.query(Transaction).filter(
            Transaction.sender_id == sender.id,
            Transaction.receiver_id == receiver.id,
        ).first() is not None
        new_counterparty_threshold = _scaled_threshold(
            account_scale, NEW_COUNTERPARTY_MIN_FRACTION, NEW_COUNTERPARTY_ABS_FLOOR
        )
        if not seen_before and amount >= new_counterparty_threshold:
            fired.append((SEVERITY_MEDIUM,
                f"New-counterparty rule: first-ever transaction to this account, "
                f"combined with a large amount ({CURRENCY_SYMBOL} {amount:,.0f})."
            ))

    # ---- Rule 3 [HIGH]: Large fraction of balance moved at once (threshold scales with balance) ----
    balance_drain_fraction_threshold = _balance_drain_fraction_threshold(sender.balance)
    if (
        sender.balance > 0
        and amount >= BALANCE_DRAIN_MIN_AMOUNT
        and (amount / sender.balance) >= balance_drain_fraction_threshold
    ):
        fired.append((SEVERITY_HIGH,
            f"Balance-drain rule: this transaction moves "
            f"{(amount / sender.balance) * 100:.0f}% of the account's current balance "
            f"({CURRENCY_SYMBOL} {amount:,.0f}), above this account's "
            f"{balance_drain_fraction_threshold * 100:.0f}% threshold."
        ))

    # ---- Rule 4 [HIGH]: ATM password attempts ----
    if failed_password_attempts >= FAILED_PASSWORD_ATTEMPTS_THRESHOLD:
        print("[RULES] ATM-password rule triggered: "
              f"{failed_password_attempts} failed password attempts before success.")
        fired.append((SEVERITY_HIGH,
            f"ATM-password rule: {failed_password_attempts} incorrect password attempts "
            f"were made on this account immediately before this withdrawal succeeded."
        ))

    # ---- Rule 5 [MEDIUM]: Amount far above this account's own typical size ----
    if len(past_amounts_legit) >= 3:
        if (
            avg_legit_amount > 0
            and amount >= ANOMALOUS_AMOUNT_MIN_FLOOR
            and amount >= avg_legit_amount * AMOUNT_MULTIPLIER_VS_AVERAGE
        ):
            fired.append((SEVERITY_LOW,
                f"Anomalous-amount rule: this transaction ({CURRENCY_SYMBOL} {amount:,.0f}) is over "
                f"{AMOUNT_MULTIPLIER_VS_AVERAGE}x this account's average of {CURRENCY_SYMBOL} {avg_legit_amount:,.0f}."
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

    # ---- Rule 7 [LOW]: Suspiciously round large amount (scaled) ----
    round_amount_threshold = _scaled_threshold(
        account_scale, ROUND_AMOUNT_FRACTION, ROUND_AMOUNT_ABS_FLOOR
    )
    if amount >= round_amount_threshold and amount % 10000 == 0:
        fired.append((SEVERITY_LOW,
            f"Round-amount rule: {CURRENCY_SYMBOL} {amount:,.0f} is an unusually round figure for a "
            f"transaction this large."
        ))

    # ---- Rule 8a [HIGH]: New IP ----
    if ip_address and getattr(sender, "last_ip", None) and sender.last_ip != ip_address:
        fired.append((SEVERITY_HIGH,
            "New-IP rule: this transaction came from a different IP address "
            "than this account's last known IP."
        ))

    # ---- Rule 8b [LOW]: New device ----
    if device and getattr(sender, "last_device", None) and sender.last_device != device:
        fired.append((SEVERITY_LOW,
            "New-device rule: this transaction came from a different device/browser "
            "than this account's last known device."
        ))

    # ---- Rule 9 [HIGH]: Rapid balance depletion across multiple transactions ----
    # Fraction threshold scales with balance via the same helper as rule 3
    # (_balance_drain_fraction_threshold). Only sums LEGIT transactions,
    # since blocked ones never actually moved money.
    drain_window_start = now - timedelta(minutes=RAPID_DRAIN_WINDOW_MINUTES)
    past_sent_in_window = sum(
        t.amount for t in legit_scored_tx
        if _as_naive_utc(t.timestamp) and _as_naive_utc(t.timestamp) >= drain_window_start
    )
    total_sent_recently = past_sent_in_window + amount
    rapid_drain_fraction_threshold = _balance_drain_fraction_threshold(sender.balance)
    if (
        sender.balance > 0
        # Requires at least one PRIOR legit transaction inside the window -
        # otherwise this is just the current transaction alone reaching the
        # threshold by itself, which is a single large transaction (already
        # Rule 3's job), not a "multiple transactions" rapid-drain pattern.
        and past_sent_in_window > 0
        and total_sent_recently >= RAPID_DRAIN_MIN_TOTAL
        and total_sent_recently >= sender.balance * rapid_drain_fraction_threshold
    ):
        fired.append((SEVERITY_HIGH,
            f"Rapid balance-drain rule: {CURRENCY_SYMBOL} {total_sent_recently:,.0f} sent across "
            f"multiple transactions in the last {RAPID_DRAIN_WINDOW_MINUTES} minutes - "
            f"{(total_sent_recently / sender.balance) * 100:.0f}% of the account's balance, "
            f"above this account's {rapid_drain_fraction_threshold * 100:.0f}% threshold."
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

    # ---- Rule 11 [MEDIUM]: Dormant account suddenly reactivated (scaled) ----
    last_tx = max(scored_sender_tx, key=lambda t: t.timestamp) if scored_sender_tx else None
    dormant_amount_threshold = _scaled_threshold(
        account_scale, DORMANT_MIN_FRACTION, DORMANT_ABS_FLOOR
    )
    if last_tx and last_tx.timestamp:
        idle_days = (now - _as_naive_utc(last_tx.timestamp)).days
        if idle_days >= DORMANT_DAYS_THRESHOLD and amount >= dormant_amount_threshold:
            fired.append((SEVERITY_MEDIUM,
                f"Dormant-account rule: first transaction after {idle_days} days of "
                f"inactivity, for {CURRENCY_SYMBOL} {amount:,.0f}."
            ))

    # ---- Rule 12 [MEDIUM]: Large transfer from a new/young account (scaled) ----
    past_tx_count = len(past_amounts_all)
    account_age_days = (
        (now - _as_naive_utc(sender.created_at)).days
        if getattr(sender, "created_at", None) else None
    )
    new_account_threshold = _scaled_threshold(
        account_scale, NEW_ACCOUNT_MIN_FRACTION, NEW_ACCOUNT_ABS_FLOOR
    )
    if (
        past_tx_count < NEW_ACCOUNT_MAX_TX_COUNT
        and account_age_days is not None
        and account_age_days <= NEW_ACCOUNT_MAX_AGE_DAYS
        and amount >= new_account_threshold
    ):
        fired.append((SEVERITY_MEDIUM,
            f"New-account rule: account is {account_age_days} days old with only "
            f"{past_tx_count} prior transactions, now sending {CURRENCY_SYMBOL} {amount:,.0f}."
        ))

    # ---- Rule 13 [MEDIUM]: Sudden spike vs. the immediately previous transaction (scaled floor) ----
    spike_floor = _scaled_threshold(account_scale, SPIKE_MIN_FRACTION, SPIKE_ABS_FLOOR)
    if last_tx and amount >= spike_floor and last_tx.amount > 0:
        if amount >= last_tx.amount * SPIKE_MULTIPLIER_VS_PREVIOUS:
            fired.append((SEVERITY_MEDIUM,
                f"Transaction-spike rule: {CURRENCY_SYMBOL} {amount:,.0f} is over "
                f"{SPIKE_MULTIPLIER_VS_PREVIOUS}x this account's previous transaction of "
                f"{CURRENCY_SYMBOL} {last_tx.amount:,.0f}."
            ))

    # ---- Rule 14 [HIGH]: Multiple recent fraud blocks from this sender ----
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

    # ---- Rule 15 [MEDIUM]: High total spending today (scaled) ----
    today_start = datetime.combine(now.date(), datetime.min.time())
    daily_total = sum(
        t.amount for t in legit_scored_tx
        if _as_naive_utc(t.timestamp) and _as_naive_utc(t.timestamp) >= today_start
    ) + amount
    daily_spend_threshold = _scaled_threshold(
        account_scale, DAILY_SPEND_FRACTION, DAILY_SPEND_ABS_FLOOR
    )
    if daily_total >= daily_spend_threshold:
        fired.append((SEVERITY_MEDIUM,
            f"Daily-limit rule: {CURRENCY_SYMBOL} {daily_total:,.0f} sent today across all "
            f"transactions, exceeding this account's normal daily threshold."
        ))

    # ---- Rule 16 [HIGH]: Receiver lock ----
    if receiver is not None and type_ == "TRANSFER":
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

    total_score = sum(weight for weight, _ in fired)
    reasons = [text for _, text in fired]
    triggered = total_score >= BLOCK_SCORE_THRESHOLD

    if fired:
        print(f"[RULES] {len(fired)} rule(s) fired, total score={total_score} "
              f"(threshold={BLOCK_SCORE_THRESHOLD}, account_scale={account_scale:,.0f}) "
              f"-> {'BLOCKED' if triggered else 'allowed (below threshold)'}")

    return (triggered, reasons if triggered else [])

