import { useEffect, useState } from "react";
import api from "../api";
import StampBadge from "../components/StampBadge";

const TYPES = ["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN", "DEBIT"];

export default function Home() {
  const [users, setUsers] = useState([]);
  const [senderId, setSenderId] = useState("");
  const [receiverId, setReceiverId] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState("TRANSFER");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .get("/api/users")
      .then((res) => setUsers(res.data))
      .catch(() => setError("Could not load accounts. Is the backend running?"));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);

    if (!senderId || !receiverId || !amount) {
      setError("Fill in sender, receiver, and amount.");
      return;
    }
    if (senderId === receiverId) {
      setError("Sender and receiver must be different accounts.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("/api/transactions", {
        sender_id: Number(senderId),
        receiver_id: Number(receiverId),
        amount: Number(amount),
        type,
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong submitting this transaction.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container">
        <div className="eyebrow">Live transfer</div>
        <h1 className="page-title">Send money, checked in real time</h1>
        <p className="page-subtitle">
          Every transfer is scored by the fraud detection model before it settles.
          Pick an account, choose a type, and enter an amount.
        </p>

        <div className="card">
          <div className="card-title">New transaction</div>
          {error && <div className="error-banner">{error}</div>}

          <form onSubmit={submit}>
            <div className="field-row">
              <div className="field">
                <label>Sender</label>
                <select value={senderId} onChange={(e) => setSenderId(e.target.value)}>
                  <option value="">Select account</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      #{u.id} — {u.full_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Receiver</label>
                <select value={receiverId} onChange={(e) => setReceiverId(e.target.value)}>
                  <option value="">Select account</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      #{u.id} — {u.full_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="field-row">
              <div className="field">
                <label>Amount</label>
                <input
                  type="number"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  min="1"
                  step="0.01"
                />
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
              {loading ? "Checking transaction…" : "Submit transfer"}
            </button>
          </form>

          <StampBadge result={result} />
        </div>

        {users.length === 0 && !error && (
          <p className="helper-text" style={{ marginTop: 16 }}>
            No accounts yet — ask an admin to add users from the admin portal.
          </p>
        )}
      </div>
    </div>
  );
}
