import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { authHeader } from "../api";
import StampBadge from "../components/StampBadge";

const TYPES = ["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN", "DEBIT"];

export default function Transfer() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [history, setHistory] = useState([]);

  const [receiverPhone, setReceiverPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState("TRANSFER");
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadProfile = () => {
    api
      .get("/api/me", { headers: authHeader("user") })
      .then((res) => setProfile(res.data))
      .catch(() => {
        localStorage.removeItem("user_token");
        navigate("/login");
      });
  };

  const loadHistory = () => {
    api
      .get("/api/transactions/me", { headers: authHeader("user") })
      .then((res) => setHistory(res.data))
      .catch(() => {});
  };

  useEffect(() => {
    if (!localStorage.getItem("user_token")) {
      navigate("/login");
      return;
    }
    loadProfile();
    loadHistory();
  }, []);

  const validate = () => {
    const errs = {};
    const cleanedPhone = receiverPhone.trim();
    if (!cleanedPhone) {
      errs.receiverPhone = "Enter the destination phone number.";
    } else if (!/^\+?[0-9]{7,15}$/.test(cleanedPhone)) {
      errs.receiverPhone = "Enter a valid phone number (7-15 digits).";
    } else if (profile && cleanedPhone === profile.phone_number) {
      errs.receiverPhone = "You cannot send money to your own number.";
    }

    const amt = Number(amount);
    if (!amount) {
      errs.amount = "Enter an amount.";
    } else if (isNaN(amt) || amt <= 0) {
      errs.amount = "Amount must be a positive number.";
    } else if (profile && amt > profile.balance) {
      errs.amount = "Amount exceeds your current balance.";
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
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
        { receiver_phone: receiverPhone.trim(), amount: Number(amount), type },
        { headers: authHeader("user") }
      );
      setResult(res.data);
      setReceiverPhone("");
      setAmount("");
      loadProfile();
      loadHistory();
    } catch (err) {
      setApiError(err.response?.data?.detail || "Something went wrong submitting this transaction.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container">
        <div className="eyebrow">Live transfer</div>
        <h1 className="page-title">Send money</h1>
        <p className="page-subtitle">
          Enter the recipient's phone number — like a mobile wallet account
          number. Every transfer is scored by the fraud model in real time.
        </p>

        {profile && (
          <div className="balance-chip">
            <span className="label">Your balance</span>
            <span className="value">Rs {Number(profile.balance).toLocaleString()}</span>
          </div>
        )}

        <div className="card">
          <div className="card-title">New transaction</div>
          {apiError && <div className="error-banner">{apiError}</div>}

          <form onSubmit={submit} noValidate>
            <div className={`field ${errors.receiverPhone ? "has-error" : ""}`}>
              <label>Destination phone number</label>
              <input
                value={receiverPhone}
                onChange={(e) => setReceiverPhone(e.target.value)}
                placeholder="e.g. 03211234567"
              />
              {errors.receiverPhone && <div className="field-error">{errors.receiverPhone}</div>}
            </div>

            <div className="field-row">
              <div className={`field ${errors.amount ? "has-error" : ""}`}>
                <label>Amount</label>
                <input
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
                <label>Transaction type</label>
                <select value={type} onChange={(e) => setType(e.target.value)}>
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button className="btn" type="submit" disabled={loading}>
              {loading ? "Checking transaction…" : "Send"}
            </button>
          </form>

          <StampBadge result={result} />
        </div>

        <div className="card">
          <div className="card-title">My transaction history</div>
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
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id}>
                      <td>
                        <span className={`direction-tag ${h.direction}`}>{h.direction}</span>
                      </td>
                      <td>{h.counterpart_name} ({h.counterpart_phone})</td>
                      <td>{h.type}</td>
                      <td>Rs {Number(h.amount).toLocaleString()}</td>
                      <td>
                        <span className={`tag ${h.prediction === "fraud" ? "fraud" : "legit"}`}>
                          {h.prediction}
                        </span>
                      </td>
                      <td>{new Date(h.timestamp).toLocaleString()}</td>
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
