import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("users");

  const [users, setUsers] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [fraudLogs, setFraudLogs] = useState([]);
  const [error, setError] = useState("");

  const [form, setForm] = useState({ full_name: "", email: "", password: "", balance: "" });
  const [submitting, setSubmitting] = useState(false);
  const [formMsg, setFormMsg] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) {
      navigate("/admin/login");
      return;
    }
    loadAll();
  }, []);

  const handleAuthError = (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("admin_token");
      navigate("/admin/login");
    } else {
      setError(err.response?.data?.detail || "Something went wrong.");
    }
  };

  const loadAll = () => {
    api.get("/api/admin/users").then((r) => setUsers(r.data)).catch(handleAuthError);
    api.get("/api/admin/transactions").then((r) => setTransactions(r.data)).catch(handleAuthError);
    api.get("/api/admin/fraud-logs").then((r) => setFraudLogs(r.data)).catch(handleAuthError);
  };

  const submitUser = async (e) => {
    e.preventDefault();
    setFormMsg("");
    setSubmitting(true);
    try {
      await api.post("/api/admin/users", {
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        balance: Number(form.balance) || 0,
      });
      setForm({ full_name: "", email: "", password: "", balance: "" });
      setFormMsg("User created.");
      loadAll();
    } catch (err) {
      setFormMsg(err.response?.data?.detail || "Could not create user.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="container">
        <div className="eyebrow">Admin portal</div>
        <h1 className="page-title">Accounts &amp; transaction monitoring</h1>
        <p className="page-subtitle">
          Add accounts, and review every transaction the model has scored.
        </p>

        {error && <div className="error-banner">{error}</div>}

        <div className="tabs">
          <button className={`tab ${tab === "users" ? "active" : ""}`} onClick={() => setTab("users")}>
            Users ({users.length})
          </button>
          <button
            className={`tab ${tab === "transactions" ? "active" : ""}`}
            onClick={() => setTab("transactions")}
          >
            Transactions ({transactions.length})
          </button>
          <button
            className={`tab ${tab === "fraud" ? "active" : ""}`}
            onClick={() => setTab("fraud")}
          >
            Fraud logs ({fraudLogs.length})
          </button>
        </div>

        {tab === "users" && (
          <>
            <div className="card">
              <div className="card-title">Add a new user</div>
              {formMsg && <p className="helper-text">{formMsg}</p>}
              <form onSubmit={submitUser}>
                <div className="field-row">
                  <div className="field">
                    <label>Full name</label>
                    <input
                      value={form.full_name}
                      onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="field">
                    <label>Email</label>
                    <input
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      required
                    />
                  </div>
                </div>
                <div className="field-row">
                  <div className="field">
                    <label>Password</label>
                    <input
                      type="password"
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      required
                    />
                  </div>
                  <div className="field">
                    <label>Starting balance</label>
                    <input
                      type="number"
                      value={form.balance}
                      onChange={(e) => setForm({ ...form, balance: e.target.value })}
                    />
                  </div>
                </div>
                <button className="btn" type="submit" disabled={submitting}>
                  {submitting ? "Adding…" : "Add user"}
                </button>
              </form>
            </div>

            <div className="card">
              <div className="card-title">All users</div>
              {users.length === 0 ? (
                <div className="empty-state">No users yet — add one above.</div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((u) => (
                        <tr key={u.id}>
                          <td>#{u.id}</td>
                          <td>{u.full_name}</td>
                          <td>{u.email}</td>
                          <td>Rs {Number(u.balance).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {tab === "transactions" && (
          <div className="card">
            <div className="card-title">All transactions</div>
            {transactions.length === 0 ? (
              <div className="empty-state">No transactions yet.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Sender</th>
                      <th>Receiver</th>
                      <th>Type</th>
                      <th>Amount</th>
                      <th>Score</th>
                      <th>Result</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((t) => (
                      <tr key={t.id}>
                        <td>#{t.id}</td>
                        <td>#{t.sender_id}</td>
                        <td>#{t.receiver_id}</td>
                        <td>{t.type}</td>
                        <td>Rs {Number(t.amount).toLocaleString()}</td>
                        <td>{t.fraud_probability?.toFixed(4)}</td>
                        <td>
                          <span className={`tag ${t.prediction === "fraud" ? "fraud" : "legit"}`}>
                            {t.prediction}
                          </span>
                        </td>
                        <td>{new Date(t.timestamp).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {tab === "fraud" && (
          <div className="card">
            <div className="card-title">Flagged transactions</div>
            {fraudLogs.length === 0 ? (
              <div className="empty-state">No fraud flagged yet.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Log ID</th>
                      <th>Transaction</th>
                      <th>Score</th>
                      <th>Threshold</th>
                      <th>Reason</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fraudLogs.map((f) => (
                      <tr key={f.id}>
                        <td>#{f.id}</td>
                        <td>#{f.transaction_id}</td>
                        <td>{f.model_score?.toFixed(4)}</td>
                        <td>{f.threshold}</td>
                        <td style={{ whiteSpace: "normal", fontFamily: "var(--font-body)" }}>
                          {f.reason}
                        </td>
                        <td>{new Date(f.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
