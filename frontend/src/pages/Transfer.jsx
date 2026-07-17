import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { authHeader } from "../api";
import StampBadge from "../components/StampBadge";

const SCENARIOS = [
  {
    type: "TRANSFER",
    title: "Send money",
    subtitle: "Customer to customer",
    description: "A direct transfer between two customer wallets.",
    outcome: "Use this for the common transfer case where fraud can appear.",
    counterpartyLabel: "Recipient phone",
    defaultCounterparty: "03001230002",
    direction: "outgoing",
    accent: "fraud",
    scene: "transfer",
  },
  {
    type: "CASH_OUT",
    title: "ATM cash out",
    subtitle: "Withdrawal flow",
    description: "Enter your password, then key in the amount on the ATM and press OK.",
    outcome: "Use this to test blocked or approved cash withdrawal behavior.",
    counterpartyLabel: "ATM / agent phone",
    defaultCounterparty: "03009990001",
    direction: "outgoing",
    accent: "fraud",
    scene: "atm",
  },
  {
    type: "PAYMENT",
    title: "Merchant payment",
    subtitle: "Checkout terminal",
    description: "Pick a merchant to pay, like a real point-of-sale checkout.",
    outcome: "Ideal for legal payment scenarios that should look clean.",
    counterpartyLabel: "Merchant",
    defaultCounterparty: "03009991001",
    counterpartyOptions: [
      { name: "Careem", phone: "03009991001" },
      { name: "Foodpanda", phone: "03009991002" },
      { name: "Daraz", phone: "03009991003" },
    ],
    direction: "outgoing",
    accent: "legit",
    scene: "payment",
  },
  {
    type: "CASH_IN",
    title: "Cash in",
    subtitle: "Money entering",
    description: "Money enters the account from a deposit agent.",
    outcome: "This should visually read as money arriving in the wallet.",
    counterpartyLabel: "Deposit agent phone",
    defaultCounterparty: "03009990003",
    direction: "incoming",
    accent: "legit",
    scene: "cashin",
  },
  {
    type: "DEBIT",
    title: "Auto debit",
    subtitle: "Recurring deduction",
    description: "Pick a biller - a recurring bill is deducted automatically.",
    outcome: "Useful for bank fees, utilities, and scheduled deductions.",
    counterpartyLabel: "Biller",
    defaultCounterparty: "03009992001",
    counterpartyOptions: [
      { name: "K-Electric", phone: "03009992001" },
      { name: "PTCL Internet", phone: "03009992002" },
      { name: "Sui Gas", phone: "03009992003" },
    ],
    direction: "outgoing",
    accent: "legit",
    scene: "debit",
  },
];



const PHONE_REGEX = /^\+?\d{7,15}$/;
const KEYPAD_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"];
const PASSWORD_LENGTH = 6;

function getVisualStatus(scenario, result) {
  if (result?.prediction === "fraud") {
    return { approvedLabel: "Blocked", statusClass: "blocked" };
  }
  if (scenario.type === "CASH_IN") {
    return { approvedLabel: "Received", statusClass: "received" };
  }
  if (result) {
    return { approvedLabel: "Approved", statusClass: "approved" };
  }
  return { approvedLabel: "Standing by", statusClass: "idle" };
}

function ScenarioVisual({
  scenario,
  amount,
  result,
  profile,
  atmStage,
  atmPassword,
  atmError,
  atmVerifying,
  onKeyPress,
  onAtmConfirm,
  onAtmReset,
  onBackspace,
}) {
  const formattedAmount = amount ? Number(amount).toLocaleString() : "0";
  const { approvedLabel, statusClass } = getVisualStatus(scenario, result);
  const isBlocked = result?.prediction === "fraud";
  const isSettled = Boolean(result);
  const isAmountStage = atmStage === "amount";

  const okDisabled =
    scenario.scene === "atm" &&
    (isSettled ||
      atmVerifying ||
      (atmStage === "password" ? atmPassword.length !== PASSWORD_LENGTH : !amount || Number(amount) <= 0));

  return (
    <div className={`scenario-visual ${scenario.scene}`}>
      <div className="scenario-visual-top">
        <span className="scene-chip">Live preview</span>
        <span className={`scene-status ${statusClass}`}>{approvedLabel}</span>
      </div>

      {scenario.scene === "transfer" && (
        <>
          <div className="transfer-flow">
            <div className="bank-card sender">
              <div className="bank-card-chip" />
              <div className="bank-card-label">Sender</div>
              <div className="bank-card-name">{profile?.full_name || "Customer"}</div>
              <div className="bank-card-number">{profile?.phone_number || "•••• •••• ••"}</div>
            </div>

            <div className={`transfer-beam ${isSettled ? (isBlocked ? "beam-blocked" : "beam-sent") : "beam-idle"}`}>
              <div className="beam-track">
                <span className="beam-dot" />
                <span className="beam-dot" />
                <span className="beam-dot" />
              </div>
              <div className="beam-amount">Rs {formattedAmount}</div>
              <div className="beam-arrow">➜</div>
            </div>

            <div className="bank-card recipient">
              <div className="bank-card-chip" />
              <div className="bank-card-label">Recipient</div>
              <div className="bank-card-name">Wallet account</div>
              <div className="bank-card-number">{scenario.defaultCounterparty}</div>
            </div>
          </div>
          <div className="scenario-visual-footer">
            <strong>Rs {formattedAmount}</strong>
            <span>{scenario.outcome}</span>
          </div>
        </>
      )}

      {scenario.scene === "atm" && (
        <>
          <div className={`atm-machine ${isBlocked ? "atm-declined" : ""}`}>
            <div className="atm-fascia-label">SIMBANK ATM</div>
            <div className="atm-screen">
              <div className="atm-screen-glass">
                <div className="atm-screen-row">
                  <span>{atmStage === "password" ? "AUTHENTICATION" : "WITHDRAWAL"}</span>
                  <span className="atm-clock">
                    {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>

                {atmStage === "password" ? (
                  <div className="atm-screen-pin-row">
                    <span className="atm-pin-label">PASSWORD</span>
                    <div className="atm-pin-dots">
                      {Array.from({ length: PASSWORD_LENGTH }).map((_, i) => (
                        <span key={i} className={`atm-pin-dot ${i < atmPassword.length ? "filled" : ""}`} />
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="atm-screen-amount">
                    RS {formattedAmount}
                    {!isSettled && <span className="atm-cursor">▌</span>}
                  </div>
                )}

                <div className="atm-screen-msg">
                  {atmStage === "password" && !atmError && "ENTER 6-DIGIT PASSWORD"}
                  {atmStage === "password" && atmError && atmError}
                  {isAmountStage && !isSettled && !atmError && "ENTER AMOUNT, THEN PRESS OK"}
                  {isAmountStage && !isSettled && atmError && atmError}
                  {isSettled && !isBlocked && "PLEASE TAKE YOUR CASH"}
                  {isSettled && isBlocked && "TRANSACTION DECLINED"}
                </div>
              </div>
            </div>

            <div className="atm-body">
              <div className="atm-card-unit">
                <div className="atm-card-slot" />
                <div className={`atm-card ${isSettled ? "atm-card-eject" : "atm-card-inserted"}`} />
                <div className="atm-unit-label">CARD</div>
              </div>

             <div className="atm-keypad-wrap">
  <div className="atm-keypad">
    {KEYPAD_KEYS.map((key) => (
      <button
        key={key}
        type="button"
        className="atm-key"
        disabled={isSettled}
        onClick={() => onKeyPress(key)}
        aria-label={key === "*" ? "Clear all" : key === "#" ? "Backspace" : `Digit ${key}`}
      >
        {key}
      </button>
    ))}
  </div>

  {!isSettled && (
    <div className="atm-controls-row">
      <button
        type="button"
        className="atm-del-btn"
        onClick={onBackspace}
        disabled={atmStage === "password" ? atmPassword.length === 0 : amount.length === 0}
        aria-label="Delete last character"
      >
        ✕ DEL
      </button>
    </div>
  )}

  {!isSettled ? (
    <button
      type="button"
      className="atm-ok-btn"
      disabled={okDisabled}
      onClick={onAtmConfirm}
    >
      {atmVerifying ? "CHECKING…" : atmStage === "password" ? "OK" : "OK · WITHDRAW"}
    </button>
  ) : (
    <button type="button" className="atm-ok-btn atm-reset-btn" onClick={onAtmReset}>
      NEW TRANSACTION
    </button>
  )}
</div>

              <div className="atm-cash-unit">
                <div className={`atm-cash-slot ${isSettled && !isBlocked ? "dispensing" : ""}`}>
                  {isSettled && !isBlocked && (
                    <div className="atm-bills">
                      <span />
                      <span />
                      <span />
                    </div>
                  )}
                </div>
                <div className="atm-unit-label">CASH</div>
              </div>
            </div>
          </div>
          <div className="scenario-visual-footer">
            <strong>Rs {formattedAmount}</strong>
            <span>{scenario.outcome}</span>
          </div>
        </>
      )}

      {scenario.scene === "payment" && (
        <>
          <div className="merchant-terminal">
            <div className="terminal-glow" />
            <div className="terminal-brand">POS · 4471</div>
            <div className="terminal-screen">
              <div className="terminal-screen-label">AMOUNT DUE</div>
              <div className="terminal-screen-amount">Rs {formattedAmount}</div>
              <div className="terminal-screen-status">
                {!isSettled && "TAP OR INSERT CARD"}
                {isSettled && "APPROVED · THANK YOU"}
              </div>
            </div>

            <div className="terminal-nfc-row">
              <div className={`contactless-ring ${isSettled ? "tapped" : ""}`}>
                <span />
                <span />
                <span />
                <svg viewBox="0 0 24 24" className="nfc-icon">
                  <path d="M6 18a6 6 0 010-12M9 15a3 3 0 010-6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              </div>
              <div className={`payment-card ${isSettled ? "card-tapped" : "card-hover"}`}>
                <div className="payment-card-chip" />
                <div className="payment-card-wave" />
              </div>
            </div>
          </div>
          <div className="scenario-visual-footer">
            <strong>Rs {formattedAmount}</strong>
            <span>{scenario.outcome}</span>
          </div>
        </>
      )}

      {scenario.scene === "cashin" && (
        <>
          <div className="cashin-lane">
            <div className="cashin-agent">
              <div className="cashin-note n1" />
              <div className="cashin-note n2" />
              <div className="cashin-note n3" />
              <div className="cashin-agent-label">Deposit agent</div>
            </div>

            <div className="cashin-stream">
              <span />
              <span />
              <span />
              <span />
            </div>

            <div className="cashin-box">
              <div className="cashin-counter">+ Rs {formattedAmount}</div>
              <div className="cashin-wallet-label">Customer wallet</div>
              <div className="cashin-receipt">
                <div className="receipt-line" />
                <div className="receipt-line" />
                <div className="receipt-line short" />
              </div>
            </div>
          </div>
          <div className="scenario-visual-footer">
            <strong>+ Rs {formattedAmount}</strong>
            <span>{scenario.outcome}</span>
          </div>
        </>
      )}

      {scenario.scene === "debit" && (
        <>
          <div className="debit-card">
            <div className="debit-ticket">
              <div className="debit-ticket-head">
                <span className="debit-biller-badge">BILLER</span>
                <span className="debit-recurring">
                  <svg viewBox="0 0 24 24" className="debit-recur-icon">
                    <path
                      d="M4 12a8 8 0 0114-5.3M20 12a8 8 0 01-14 5.3M4 4v5h5M20 20v-5h-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  Recurring
                </span>
              </div>
              <div className="debit-ticket-amount">Rs {formattedAmount}</div>
              <div className="debit-ticket-meta">Auto-deducted from wallet balance</div>
              <div className="debit-perforation">
                {Array.from({ length: 14 }).map((_, i) => (
                  <span key={i} />
                ))}
              </div>
              <div className="debit-ticket-stub">
                <span>{isSettled ? "DEDUCTED" : "SCHEDULED"}</span>
                <span>{new Date().toLocaleDateString()}</span>
              </div>
            </div>
          </div>
          <div className="scenario-visual-footer">
            <strong>Rs {formattedAmount}</strong>
            <span>{scenario.outcome}</span>
          </div>
        </>
      )}
    </div>
  );
}

function DisputeCell({
  item, disputes, disputingId, disputeReason, disputeMsg, disputeSubmitting,
  onStart, onChange, onSubmit, onCancel,
}) {
  if (item.prediction !== "fraud" || item.direction !== "sent") {
    return <span className="helper-text">—</span>;
  }

  const dispute = disputes.find((d) => d.transaction_id === item.id);
  if (dispute) {
    return <span className={`dispute-status ${dispute.status}`}>{dispute.status}</span>;
  }

  if (disputingId === item.id) {
    return (
      <div className="dispute-form">
        <textarea
          value={disputeReason}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Why should this be reviewed?"
          rows={2}
        />
        {disputeMsg && <div className="field-error">{disputeMsg}</div>}
        <div className="dispute-form-actions">
          <button type="button" className="icon-btn" onClick={() => onSubmit(item.id)} disabled={disputeSubmitting}>
            {disputeSubmitting ? "Submitting…" : "Submit"}
          </button>
          <button type="button" className="icon-btn" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <button type="button" className="icon-btn danger" onClick={() => onStart(item.id)}>
      Dispute
    </button>
  );
}

export default function Transfer() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [history, setHistory] = useState([]);
  const [type, setType] = useState("TRANSFER");
  const [counterpartyPhone, setCounterpartyPhone] = useState("03001230002");
  const [amount, setAmount] = useState("");
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [myDisputes, setMyDisputes] = useState([]);
  const [disputingId, setDisputingId] = useState(null);
  const [disputeReason, setDisputeReason] = useState("");
  const [disputeSubmitting, setDisputeSubmitting] = useState(false);
  const [disputeMsg, setDisputeMsg] = useState("");
  const [myFraudLogs, setMyFraudLogs] = useState([]);

  // ATM-specific state
  const [atmStage, setAtmStage] = useState("password"); // "password" | "amount"
  const [atmPassword, setAtmPassword] = useState("");
  const [atmError, setAtmError] = useState("");
  const [atmVerifying, setAtmVerifying] = useState(false);

  const scenario = useMemo(() => SCENARIOS.find((item) => item.type === type) || SCENARIOS[0], [type]);
  const isAtm = scenario.type === "CASH_OUT";

  const clearSession = () => {
    localStorage.removeItem("user_token");
    localStorage.removeItem("admin_token");
  };

  const goHome = () => {
    clearSession();
    navigate("/");
  };

  const logout = () => {
    clearSession();
    navigate("/login");
  };

  const loadProfile = () => {
    api
      .get("/api/me", { headers: authHeader("user") })
      .then((res) => setProfile(res.data))
      .catch(() => {
        clearSession();
        navigate("/login");
      });
  };

  const loadHistory = () => {
    api
      .get("/api/transactions/me", { headers: authHeader("user") })
      .then((res) => setHistory(res.data))
      .catch(() => {});
  };

  const loadDisputes = () => {
    api
      .get("/api/disputes/me", { headers: authHeader("user") })
      .then((res) => setMyDisputes(res.data))
      .catch(() => {});
  };

  const loadFraudLogs = () => {
  api
    .get("/api/fraud-logs/me", { headers: authHeader("user") })
    .then((res) => setMyFraudLogs(res.data))
    .catch(() => {});
};

  const submitDispute = async (transactionId) => {
    if (!disputeReason.trim() || disputeReason.trim().length < 5) {
      setDisputeMsg("Please enter at least 5 characters explaining why this should be reviewed.");
      return;
    }
    setDisputeSubmitting(true);
    setDisputeMsg("");
    try {
      await api.post(
        `/api/transactions/${transactionId}/dispute`,
        { reason: disputeReason.trim() },
        { headers: authHeader("user") }
      );
      setDisputingId(null);
      setDisputeReason("");
      loadDisputes();
    } catch (err) {
      setDisputeMsg(err.response?.data?.detail || "Could not submit dispute.");
    } finally {
      setDisputeSubmitting(false);
    }
  };

  

  useEffect(() => {
  if (!localStorage.getItem("user_token")) {
    navigate("/login");
    return;
  }
  loadProfile();
  loadHistory();
  loadDisputes();
  loadFraudLogs();
}, [navigate]);

  const resetAtm = () => {
    setAtmStage("password");
    setAtmPassword("");
    setAtmError("");
    setAtmVerifying(false);
    setAmount("");
    setResult(null);
    setApiError("");
  };

  useEffect(() => {
    setCounterpartyPhone(scenario.defaultCounterparty);
    setErrors({});
    resetAtm();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario.defaultCounterparty]);

  const handleKeypadPress = (key) => {
    if (atmStage === "password") {
      if (key === "*") {
        setAtmPassword("");
        setAtmError("");
        return;
      }
      if (key === "#") {
        setAtmPassword((prev) => prev.slice(0, -1));
        return;
      }
      setAtmPassword((prev) => (prev.length < PASSWORD_LENGTH ? prev + key : prev));
      return;
    }

    // amount stage
    if (key === "*") {
      setAmount("");
      setAtmError("");
      return;
    }
    if (key === "#") {
      setAmount((prev) => prev.slice(0, -1));
      return;
    }
    setAmount((prev) => (prev.length < 9 ? prev + key : prev));
  };

  const handleBackspace = () => {
  if (atmStage === "password") {
    setAtmPassword((prev) => prev.slice(0, -1));
    setAtmError("");
    return;
  }
  setAmount((prev) => prev.slice(0, -1));
  setAtmError("");
};

  const handleAtmConfirm = async () => {
    if (atmStage === "password") {
      if (atmPassword.length !== PASSWORD_LENGTH) {
        setAtmError("ENTER ALL 6 DIGITS");
        return;
      }
      setAtmError("");
      setAtmVerifying(true);
      try {
        const res = await api.post(
          "/api/verify-password",
          { password: atmPassword },
          { headers: authHeader("user") }
        );
        if (res.data?.valid) {
          setAtmStage("amount");
          setAtmPassword("");
          setAmount("");
        } else {
          setAtmError("INCORRECT PASSWORD");
          setAtmPassword("");
        }
      } catch (err) {
        setAtmError(err.response?.data?.detail || "COULD NOT VERIFY PASSWORD");
        setAtmPassword("");
      } finally {
        setAtmVerifying(false);
      }
      return;
    }

    // amount stage — validate then withdraw
    const value = Number(amount);
    if (!amount || Number.isNaN(value) || value <= 0) {
      setAtmError("ENTER A VALID AMOUNT");
      return;
    }
    if (profile && value > profile.balance) {
      setAtmError("AMOUNT EXCEEDS BALANCE");
      return;
    }

    setAtmError("");
    setLoading(true);
    setApiError("");
    try {
      const res = await api.post(
        "/api/transactions",
        {
          counterparty_phone: scenario.defaultCounterparty,
          amount: value,
          type: "CASH_OUT",
        },
        { headers: authHeader("user") }
      );
      setResult(res.data);
      loadProfile();
      loadHistory();
      loadFraudLogs();
    } catch (err) {
      setApiError(err.response?.data?.detail || "Something went wrong submitting this transaction.");
    } finally {
      setLoading(false);
    }
  };

const getFraudReason = (transactionId) => {
  const log = myFraudLogs.find((f) => f.transaction_id === transactionId);
  return log?.reason || null;
};

  const validate = () => {
    const nextErrors = {};
    const cleanedPhone = counterpartyPhone.trim();

    if (!cleanedPhone) {
      nextErrors.counterpartyPhone = `Enter the ${scenario.counterpartyLabel.toLowerCase()}.`;
    } else if (!PHONE_REGEX.test(cleanedPhone)) {
      nextErrors.counterpartyPhone = "Enter a valid phone number (7-15 digits).";
    } else if (cleanedPhone === profile?.phone_number) {
      nextErrors.counterpartyPhone = "You cannot use your own account as the counterparty.";
    }

    const value = Number(amount);
    if (!amount) {
      nextErrors.amount = "Enter an amount.";
    } else if (Number.isNaN(value) || value <= 0) {
      nextErrors.amount = "Amount must be a positive number.";
    } else if (scenario.direction === "outgoing" && profile && value > profile.balance) {
      nextErrors.amount = "Amount exceeds your current balance.";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const submit = async (e) => {
    e.preventDefault();
    setApiError("");
    setResult(null);
    if (!validate()) return;

    setLoading(true);
    try {
      const res = await api.post(
        "/api/transactions",
        {
          counterparty_phone: counterpartyPhone.trim(),
          amount: Number(amount),
          type,
        },
        { headers: authHeader("user") }
      );
      setResult(res.data);
      setAmount("");
      loadProfile();
      loadHistory();
      loadFraudLogs();
    } catch (err) {
      setApiError(err.response?.data?.detail || "Something went wrong submitting this transaction.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container bank-shell">
        <div className="page-actions">
          <button type="button" className="icon-btn" onClick={goHome}>
            Home
          </button>
          <button type="button" className="icon-btn danger" onClick={logout}>
            Logout
          </button>
        </div>

        <div className="eyebrow">Customer console</div>
        <h1 className="page-title">Private bank simulator</h1>
        <p className="page-subtitle">
          Five real-feeling transaction scenes. Use the preview to understand the flow, then submit
          the transaction and inspect the result instantly.
        </p>

        <div className="customer-dashboard-grid">
          <div className="customer-main-column">
            {profile && (
              <div className="card profile-card">
                <div className="card-title">Logged in customer</div>
                <div className="profile-row">
                  <span>Name</span>
                  <strong>{profile.full_name}</strong>
                </div>
                <div className="profile-row">
                  <span>Email</span>
                  <strong>{profile.email}</strong>
                </div>
                <div className="profile-row">
                  <span>Phone</span>
                  <strong>{profile.phone_number}</strong>
                </div>
                <div className="profile-row profile-row-highlight">
                  <span>Available balance</span>
                  <strong>Rs {Number(profile.balance).toLocaleString()}</strong>
                </div>
              </div>
            )}

            <div className="card">
              <div className="card-title">Choose a flow</div>
              <div className="scenario-selector">
                {SCENARIOS.map((item) => (
                  <button
                    key={item.type}
                    type="button"
                    className={`scenario-tile ${type === item.type ? "active" : ""}`}
                    onClick={() => {
                      setType(item.type);
                      setCounterpartyPhone(item.defaultCounterparty);
                      setResult(null);
                      setApiError("");
                    }}
                  >
                    <div className="scenario-tile-head">
                      <span>{item.title}</span>
                      <span className={`scenario-pulse ${item.accent}`} />
                    </div>
                    <p>{item.subtitle}</p>
                    <small>{item.outcome}</small>
                  </button>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-title">Live bank scene</div>
              <ScenarioVisual
                scenario={scenario}
                amount={amount}
                result={result}
                profile={profile}
                atmStage={atmStage}
                atmPassword={atmPassword}
                atmError={atmError}
                atmVerifying={atmVerifying}
                onKeyPress={handleKeypadPress}
                onAtmConfirm={handleAtmConfirm}
                onAtmReset={resetAtm}
                 onBackspace={handleBackspace}
              />
            </div>

            <div className="card">
              <div className="card-title">Run transaction</div>
              {apiError && <div className="error-banner">{apiError}</div>}

              {isAtm ? (
                <div className="atm-form-note">
                  {atmStage === "password"
                    ? "Enter your 6-digit password on the ATM keypad above, then press OK."
                    : "Enter the cash amount on the ATM keypad above, then press OK · WITHDRAW."}
                </div>
              ) : (
                <form onSubmit={submit} noValidate>
                  <div className={`field ${errors.counterpartyPhone ? "has-error" : ""}`}>
                    <label>{scenario.counterpartyLabel}</label>

                    {scenario.counterpartyOptions ? (
                      <div className="option-list">
                        {scenario.counterpartyOptions.map((opt) => (
                          <button
                            key={opt.phone}
                            type="button"
                            className={`option-pill ${counterpartyPhone === opt.phone ? "active" : ""}`}
                            onClick={() => setCounterpartyPhone(opt.phone)}
                          >
                            {opt.name}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <input
                        id="counterparty-phone"
                        value={counterpartyPhone}
                        onChange={(e) => setCounterpartyPhone(e.target.value)}
                        placeholder={scenario.defaultCounterparty}
                      />
                    )}

                    {errors.counterpartyPhone && <div className="field-error">{errors.counterpartyPhone}</div>}
                    <div className="helper-text">{scenario.description}</div>
                  </div>

                  <div className="field-row">
                    <div className={`field ${errors.amount ? "has-error" : ""}`}>
                      <label htmlFor="tx-amount">Amount</label>
                      <input
                        id="tx-amount"
                        type="number"
                        placeholder="0.00"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        min="1"
                        step="0.01"
                      />
                      {errors.amount && <div className="field-error">{errors.amount}</div>}
                    </div>
                    <div className="field">
                      <div className="field-label">Active flow</div>
                      <div id="active-flow" className="active-flow-pill">
                        {scenario.title}
                      </div>
                    </div>
                  </div>

                  <button className="btn" type="submit" disabled={loading}>
                    {loading ? "Checking transaction…" : `Run ${scenario.type.toLowerCase()} scenario`}
                  </button>
                </form>
              )}

              <StampBadge result={result} />
            </div>
          </div>

          <div className="customer-side-column">
            <div className="card scenario-summary-card">
              <div className="card-title">Scenario details</div>
              <div className={`scenario-badge ${scenario.accent}`}>{scenario.title}</div>
              <div className="scenario-subtitle">{scenario.subtitle}</div>
              <p className="scenario-copy">{scenario.description}</p>
              <div className="scenario-note">{scenario.outcome}</div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Transaction history</div>
          {history.length === 0 ? (
            <div className="empty-state">No transactions yet.</div>
          ) : (
            <div className="table-wrap">
             <table>
  <thead>
    <tr>
      <th>Direction</th>
      <th>With</th>
      <th>Type</th>
      <th>Amount</th>
      <th>Result</th>
      <th>Reason</th>
      <th>Dispute</th>
      <th>Date & Time</th>
    </tr>
  </thead>
  <tbody>
    {history.map((item) => (
      <tr key={item.id}>
        <td>
          <span className={`direction-tag ${item.direction}`}>{item.direction}</span>
        </td>
        <td>
          {item.counterpart_name} ({item.counterpart_phone})
        </td>
        <td>{item.type}</td>
        <td>Rs {Number(item.amount).toLocaleString()}</td>
        <td>
          <span className={`tag ${item.prediction === "fraud" ? "fraud" : "legit"}`}>
            {item.prediction}
          </span>
        </td>
        <td className="reason-cell">
          {item.prediction === "fraud" ? (getFraudReason(item.id) || "Flagged by fraud model") : "—"}
        </td>
        <td>
          <DisputeCell
            item={item}
            disputes={myDisputes}
            disputingId={disputingId}
            disputeReason={disputeReason}
            disputeMsg={disputeMsg}
            disputeSubmitting={disputeSubmitting}
            onStart={(id) => {
              setDisputingId(id);
              setDisputeReason("");
              setDisputeMsg("");
            }}
            onChange={setDisputeReason}
            onSubmit={submitDispute}
            onCancel={() => {
              setDisputingId(null);
              setDisputeReason("");
              setDisputeMsg("");
            }}
          />
        </td>
        <td>{new Date(item.timestamp).toLocaleString()}</td>
      </tr>
    ))}
  </tbody>
</table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}