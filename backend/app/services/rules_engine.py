from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.constants import CURRENCY_SYMBOL


SEVERITY_HIGH = 3     # strong enough to block completely alone
SEVERITY_MEDIUM = 2   # real signal, but not alone-worthy
SEVERITY_LOW = 1      # weak signal, only meaningful combined with others
BLOCK_SCORE_THRESHOLD = 3

# Transaction types that never get scored by this engine, and whose history
# is excluded when scoring OTHER (non-exempt) transactions too.
NON_SCORED_TYPES = ("PAYMENT", "DEBIT")


ACCOUNT_SCALE_FLOOR = 5000


def _account_scale(sender_balance: float, legit_avg_amount: float) -> float:
    return max(sender_balance or 0, legit_avg_amount or 0, ACCOUNT_SCALE_FLOOR)


def _scaled_threshold(scale: float, fraction: float, absolute_floor: float) -> float:
    """The amount a transaction must reach before a rule considers it
    'large' for THIS account - whichever is bigger: the fixed floor (so
    trivial accounts aren't flagged over pocket change), or a fraction of
    this account's own scale (so a large-balance account isn't flagged over
    an amount that's routine for them)."""
    return max(absolute_floor, scale * fraction)


# ---- Tunable thresholds - adjust these based on what you see in testing ----
VELOCITY_WINDOW_MINUTES = 10
VELOCITY_MAX_TRANSACTIONS = 3

# Rule 2: new counterparty + large amount - now scaled to account size
NEW_COUNTERPARTY_MIN_FRACTION = 0.15   # 15% of this account's scale
NEW_COUNTERPARTY_ABS_FLOOR = 20000     # ...but never below this fixed floor

LARGE_FRACTION_OF_BALANCE = 0.9          # rule 3 - already relative, unchanged
BALANCE_DRAIN_MIN_AMOUNT = 20000         # small fixed floor, filters trivial balances only

AMOUNT_MULTIPLIER_VS_AVERAGE = 5          # rule 5 - already relative to this account's own average
ANOMALOUS_AMOUNT_MIN_FLOOR = 20000        # small fixed floor, filters trivial averages only

REPEAT_COUNTERPARTY_WINDOW_MINUTES = 15
REPEAT_COUNTERPARTY_MAX_COUNT = 2

# Rule 7: round large amount - now scaled to account size
ROUND_AMOUNT_FRACTION = 0.15
ROUND_AMOUNT_ABS_FLOOR = 20000

# ATM password attempts: the frontend allows 3 total tries before locking the
# card. 2+ wrong attempts before the successful one is treated as suspicious.
FAILED_PASSWORD_ATTEMPTS_THRESHOLD = 2

RAPID_DRAIN_WINDOW_MINUTES = 10
RAPID_DRAIN_FRACTION = 0.9                # rule 9 - already relative, unchanged
RAPID_DRAIN_MIN_TOTAL = 20000             # small fixed floor, filters trivial balances only

FAN_OUT_WINDOW_MINUTES = 20
FAN_OUT_MIN_DISTINCT_RECEIVERS = 4

DORMANT_DAYS_THRESHOLD = 90
# Rule 11: dormant account reactivated - now scaled to account size
DORMANT_MIN_FRACTION = 0.10
DORMANT_ABS_FLOOR = 15000

NEW_ACCOUNT_MAX_TX_COUNT = 5
NEW_ACCOUNT_MAX_AGE_DAYS = 30
# Rule 12: large transfer from a new/young account - now scaled to account size
NEW_ACCOUNT_MIN_FRACTION = 0.15
NEW_ACCOUNT_ABS_FLOOR = 20000

SPIKE_MULTIPLIER_VS_PREVIOUS = 20
# Rule 13: sudden spike vs previous transaction - floor now scaled to account size
SPIKE_MIN_FRACTION = 0.10
SPIKE_ABS_FLOOR = 15000

RECENT_FRAUD_WINDOW_HOURS = 1
RECENT_FRAUD_MAX_COUNT = 3

# Rule 15: high total spending today - now scaled to account size
DAILY_SPEND_FRACTION = 0.5                # 50% of this account's scale, in one day
DAILY_SPEND_ABS_FLOOR = 100000

# Receiver lock: same rolling-window "lock" pattern as the ATM card lock,
# but on the receiving side. 3+ fraud-flagged transactions TO this receiver
# within a 2-day window reads as "this account is temporarily locked from
# receiving". Rolling window, not a stored lock timestamp - self-clears once
# old fraud incidents age out and the count drops back under the threshold.
RECEIVER_LOCK_FRAUD_COUNT_THRESHOLD = 3
RECEIVER_LOCK_WINDOW_DAYS = 2


def _as_naive_utc(dt):
    """Normalize a timestamp to a naive UTC datetime so every window
    comparison in this module is done on the same clock. If the column is
    timezone-aware (e.g. TIMESTAMPTZ), shift the wall-clock value by its
    offset first, THEN drop the tzinfo - don't just strip tzinfo directly,
    which would silently misinterpret e.g. `18:02:23+05` as `18:02:23 UTC`
    instead of the correct `13:02:23 UTC`.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def evaluate_rules(db: Session, sender, receiver, amount: float, type_: str,
                    ip_address: str = None, device: str = None,
                    failed_password_attempts: int = 0):
    """
    Runs all rules for one transaction attempt and scores them.
    Returns (any_rule_triggered: bool, reasons: list[str]) - "triggered"
    means the combined severity score reached BLOCK_SCORE_THRESHOLD, not
    just "at least one rule fired".
    """
    if type_ in NON_SCORED_TYPES:
        return (False, [])

    fired = []  # list of (severity_weight, reason_text)
    now = datetime.utcnow()

    # ---- Single fetch of this sender's history, reused by every rule below.
    # Excludes PAYMENT/DEBIT rows so routine bill payments and merchant
    # checkouts never inflate the score of an unrelated transfer/withdrawal.
    all_sender_tx = db.query(Transaction).filter(Transaction.sender_id == sender.id).all()
    scored_sender_tx = [t for t in all_sender_tx if t.type not in NON_SCORED_TYPES]

    # Legit-only subset: a blocked transaction never actually moved money,
    # so it shouldn't count toward "this account's average size" or "total
    # spent today". Used for the average (rule 5), rapid-drain total
    # (rule 9), daily total (rule 15), and the account-scale calculation.
    legit_scored_tx = [t for t in scored_sender_tx if t.prediction == "legit"]
    past_amounts_legit = [t.amount for t in legit_scored_tx]
    avg_legit_amount = sum(past_amounts_legit) / len(past_amounts_legit) if past_amounts_legit else 0

    # All attempts (including blocked ones) - used where the signal is about
    # ATTEMPT PATTERNS/experience rather than real money moved.
    past_amounts_all = [t.amount for t in scored_sender_tx]

    account_scale = _account_scale(sender.balance, avg_legit_amount)

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

    # ---- Rule 2 [MEDIUM]: New/unfamiliar counterparty + large amount (scaled) ----
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

    # ---- Rule 3 [HIGH]: Large fraction of balance moved at once ----
    # Already relative (a % of this account's own balance) - unchanged.
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
    # Already relative (vs. this account's own average LEGIT transaction) - unchanged.
    if len(past_amounts_legit) >= 3:
        if (
            avg_legit_amount > 0
            and amount >= ANOMALOUS_AMOUNT_MIN_FLOOR
            and amount >= avg_legit_amount * AMOUNT_MULTIPLIER_VS_AVERAGE
        ):
            fired.append((SEVERITY_MEDIUM,
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

    # ---- Rule 8a [HIGH]: New IP compared to this account's last transaction ----
    # Blocks ALONE - session hijacking/credential theft typically comes from a
    # different network than the real account owner's. Only fires once
    # last_ip is already on record (never on a user's very first transaction).
    if ip_address and getattr(sender, "last_ip", None) and sender.last_ip != ip_address:
        fired.append((SEVERITY_HIGH,
            "New-IP rule: this transaction came from a different IP address "
            "than this account's last known IP."
        ))

    # ---- Rule 8b [LOW]: New device compared to this account's last transaction ----
    # Stays weak alone - switching phones/browsers is common and usually innocent.
    if device and getattr(sender, "last_device", None) and sender.last_device != device:
        fired.append((SEVERITY_LOW,
            "New-device rule: this transaction came from a different device/browser "
            "than this account's last known device."
        ))

    # ---- Rule 9 [HIGH]: Rapid balance depletion across multiple transactions ----
    # Already relative (a % of this account's own balance) - unchanged. Only
    # sums LEGIT transactions, since blocked ones never actually moved money.
    drain_window_start = now - timedelta(minutes=RAPID_DRAIN_WINDOW_MINUTES)
    total_sent_recently = sum(
        t.amount for t in legit_scored_tx
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

    # ---- Rule 11 [MEDIUM]: Dormant account suddenly reactivated (scaled) ----
    # "Last transaction" here means the last SCORED (non-exempt) attempt,
    # including blocked ones - any attempt at all means the account wasn't
    # truly dormant. The amount floor below is what's scaled.
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
    # Transaction count uses ALL attempts (including blocked) as a proxy for
    # how established/experienced this account is - a blocked attempt still
    # means the account has been used before.
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

    # ---- Rule 13 [MEDIUM]: Sudden spike vs. the immediately previous transaction (floor scaled) ----
    spike_floor = _scaled_threshold(account_scale, SPIKE_MIN_FRACTION, SPIKE_ABS_FLOOR)
    if last_tx and amount >= spike_floor and last_tx.amount > 0:
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

    # ---- Rule 15 [MEDIUM]: High total spending today (scaled) ----
    # Only sums LEGIT transactions - blocked ones never actually left the account.
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

    # ---- Rule 16 [HIGH]: Receiver lock - repeated recent fraud landing on this account ----
    # Mirrors the ATM card-lock pattern, but for the receiving side: 3+
    # fraud-flagged transactions TO this receiver within a 2-day rolling
    # window blocks alone, like a temporary receive-side freeze. Self-clears
    # as old incidents age past RECEIVER_LOCK_WINDOW_DAYS.
    #
    # Restricted to TRANSFER only. CASH_OUT's "receiver" is the shared
    # ATM/agent phone number - every customer's withdrawal lands on the same
    # account, so unrelated blocked withdrawals would rack up fraud hits on
    # that one shared number and lock ATM withdrawals for everyone, not just
    # an account actually being used as a fraud drop point. PAYMENT/DEBIT are
    # already excluded entirely by NON_SCORED_TYPES.
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

    # ---- Score everything that fired ----
    total_score = sum(weight for weight, _ in fired)
    reasons = [text for _, text in fired]
    triggered = total_score >= BLOCK_SCORE_THRESHOLD

    if fired:
        print(f"[RULES] {len(fired)} rule(s) fired, total score={total_score} "
              f"(threshold={BLOCK_SCORE_THRESHOLD}, account_scale={account_scale:,.0f}) "
              f"-> {'BLOCKED' if triggered else 'allowed (below threshold)'}")

    return (triggered, reasons if triggered else [])