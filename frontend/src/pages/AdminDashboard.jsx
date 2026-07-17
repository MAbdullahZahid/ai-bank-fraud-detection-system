import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import api, { authHeader } from "../api";

const PHONE_REGEX = /^\+?\d{7,15}$/;

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("users");

  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [fraudLogs, setFraudLogs] = useState([]);
  const [error, setError] = useState("");
  const [disputes, setDisputes] = useState([]);

  // Add-user form
  const [form, setForm] = useState({ full_name: "", email: "", phone_number: "", password: "", balance: "" });
  const [formErrors, setFormErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [formMsg, setFormMsg] = useState("");

  // Inline edit state
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [editErrors, setEditErrors] = useState({});

  const clearSession = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("user_token");
  };

  const goHome = () => {
    clearSession();
    navigate("/");
  };

  const logout = () => {
    clearSession();
    navigate("/admin/login");
  };

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

  const resolveDispute = async (disputeId, approve) => {
    const notes = window.prompt(
      approve ? "Optional note for approving this dispute:" : "Optional note for rejecting this dispute:"
    ) || "";
    try {
      await api.post(
        `/api/admin/disputes/${disputeId}/resolve`,
        { approve, admin_notes: notes },
        { headers: authHeader("admin") }
      );
      loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not resolve dispute.");
    }
  };

  const loadAll = () => {
    const headers = { headers: authHeader("admin") };
    api.get("/api/admin/stats", headers).then((r) => setStats(r.data)).catch(handleAuthError);
    api.get("/api/admin/users", headers).then((r) => setUsers(r.data)).catch(handleAuthError);
    api.get("/api/admin/transactions", headers).then((r) => setTransactions(r.data)).catch(handleAuthError);
    api.get("/api/admin/fraud-logs", headers).then((r) => setFraudLogs(r.data)).catch(handleAuthError);
    api.get("/api/admin/disputes", headers).then((r) => setDisputes(r.data)).catch(handleAuthError);
  };

  // ---------- Add user ----------
  const validateForm = () => {
    const errs = {};
    if (!form.full_name.trim() || form.full_name.trim().length < 2) {
      errs.full_name = "Full name must be at least 2 characters.";
    }
    if (!form.email.trim() || !form.email.includes("@") || !form.email.includes(".")) {
      errs.email = "Enter a valid email address.";
    }
    if (!PHONE_REGEX.test(form.phone_number.trim())) {
      errs.phone_number = "Enter a valid phone number (7-15 digits).";
    }
    if (!form.password || form.password.length < 6) {
      errs.password = "Password must be at least 6 characters.";
    }
    if (form.balance !== "" && Number(form.balance) < 0) {
      errs.balance = "Balance cannot be negative.";
    }
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const submitUser = async (e) => {
    e.preventDefault();
    setFormMsg("");
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      const res = await api.post(
        "/api/admin/users",
        {
          full_name: form.full_name.trim(),
          email: form.email.trim(),
          phone_number: form.phone_number.trim(),
          password: form.password,
          balance: Number(form.balance) || 0,
        },
        { headers: authHeader("admin") }
      );
      setForm({ full_name: "", email: "", phone_number: "", password: "", balance: "" });
      setFormMsg(
        res.data.email_sent
          ? "User created — account details emailed to them."
          : "User created. Email was not sent (check SMTP settings in .env) — share their login details manually."
      );
      loadAll();
    } catch (err) {
      setFormMsg(err.response?.data?.detail || "Could not create user.");
    } finally {
      setSubmitting(false);
    }
  };

  // ---------- Edit user ----------
  const startEdit = (user) => {
    setEditingId(user.id);
    setEditForm({
      full_name: user.full_name,
      email: user.email,
      phone_number: user.phone_number,
      balance: user.balance,
    });
    setEditErrors({});
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm({});
    setEditErrors({});
  };

  const validateEdit = () => {
    const errs = {};
    if (!editForm.full_name || editForm.full_name.trim().length < 2) {
      errs.full_name = "Too short.";
    }
    if (!(editForm.email || "").includes("@") || !(editForm.email || "").includes(".")) {
      errs.email = "Invalid email.";
    }
    if (!PHONE_REGEX.test((editForm.phone_number || "").trim())) {
      errs.phone_number = "Invalid phone.";
    }
    if (editForm.balance !== "" && Number(editForm.balance) < 0) {
      errs.balance = "Cannot be negative.";
    }
    setEditErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const saveEdit = async (userId) => {
    if (!validateEdit()) return;
    try {
      await api.put(
        `/api/admin/users/${userId}`,
        {
          full_name: editForm.full_name.trim(),
          email: editForm.email.trim(),
          phone_number: editForm.phone_number.trim(),
          balance: Number(editForm.balance),
        },
        { headers: authHeader("admin") }
      );
      cancelEdit();
      loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not update user.");
    }
  };

  const deleteUser = async (userId, name) => {
    if (!window.confirm(`Delete ${name}? This cannot be undone.`)) return;
    try {
      await api.delete(`/api/admin/users/${userId}`, { headers: authHeader("admin") });
      loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not delete user.");
    }
  };

  const chartData = stats
    ? [
        { name: "Legitimate", count: stats.legit_count },
        { name: "Fraud", count: stats.fraud_count },
      ]
    : [];

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 1040 }}>
        <div className="page-actions">
          <button type="button" className="icon-btn" onClick={goHome}>
            Home
          </button>
          <button type="button" className="icon-btn danger" onClick={logout}>
            Logout
          </button>
        </div>
        <div className="eyebrow">Admin portal</div>
        <h1 className="page-title">Accounts &amp; transaction monitoring</h1>
        <p className="page-subtitle">
          Add and manage accounts, and review every transaction the model has scored.
        </p>

        {error && <div className="error-banner">{error}</div>}

        {stats && (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-label">Total users</div>
                <div className="stat-value">{stats.total_users}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Total transactions</div>
                <div className="stat-value">{stats.total_transactions}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Fraud detected</div>
                <div className="stat-value danger">{stats.fraud_count}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Fraud rate</div>
                <div className="stat-value gold">{stats.fraud_rate}%</div>
              </div>
            </div>

            <div className="chart-card">
              <div className="card-title">Legitimate vs. fraud</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e3e6ec" />
                  <XAxis dataKey="name" stroke="#5b6472" fontSize={12} />
                  <YAxis stroke="#5b6472" fontSize={12} />
                  <Tooltip
                    contentStyle={{ background: "#ffffff", border: "1px solid #e3e6ec", borderRadius: 8 }}
                    labelStyle={{ color: "#101828" }}
                  />
                  <Bar
                    dataKey="count"
                    radius={[4, 4, 0, 0]}
                    shape={(props) => {
                      const fill = props.payload?.name === "Fraud" ? "#d64545" : "#1f9d55";
                      return <rect x={props.x} y={props.y} width={props.width} height={props.height} fill={fill} rx={4} ry={4} />;
                    }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}

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
          <button className={`tab ${tab === "fraud" ? "active" : ""}`} onClick={() => setTab("fraud")}>
            Fraud logs ({fraudLogs.length})
          </button>
          <button className={`tab ${tab === "disputes" ? "active" : ""}`} onClick={() => setTab("disputes")}>
            Disputes ({disputes.filter((d) => d.status === "pending").length})
          </button>
        </div>

        {tab === "users" && (
          <>
            <div className="card">
              <div className="card-title">Add a new user</div>
              {formMsg && <p className="helper-text">{formMsg}</p>}
              <form onSubmit={submitUser} noValidate>
                <div className="field-row">
                  <div className={`field ${formErrors.full_name ? "has-error" : ""}`}>
                    <label htmlFor="admin-full-name">Full name</label>
                    <input
                      id="admin-full-name"
                      value={form.full_name}
                      onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    />
                    {formErrors.full_name && <div className="field-error">{formErrors.full_name}</div>}
                  </div>
                  <div className={`field ${formErrors.email ? "has-error" : ""}`}>
                    <label htmlFor="admin-email">Email</label>
                    <input
                      id="admin-email"
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                    />
                    {formErrors.email && <div className="field-error">{formErrors.email}</div>}
                  </div>
                </div>
                <div className="field-row">
                  <div className={`field ${formErrors.phone_number ? "has-error" : ""}`}>
                    <label htmlFor="admin-phone">Phone number</label>
                    <input
                      id="admin-phone"
                      value={form.phone_number}
                      onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                      placeholder="e.g. 03001234567"
                    />
                    {formErrors.phone_number && <div className="field-error">{formErrors.phone_number}</div>}
                  </div>
                  <div className={`field ${formErrors.password ? "has-error" : ""}`}>
                    <label htmlFor="admin-password-create">Password</label>
                    <input
                      id="admin-password-create"
                      type="password"
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                    />
                    {formErrors.password && <div className="field-error">{formErrors.password}</div>}
                  </div>
                </div>
                <div className={`field ${formErrors.balance ? "has-error" : ""}`}>
                  <label htmlFor="admin-balance">Starting balance</label>
                  <input
                    id="admin-balance"
                    type="number"
                    value={form.balance}
                    onChange={(e) => setForm({ ...form, balance: e.target.value })}
                  />
                  {formErrors.balance && <div className="field-error">{formErrors.balance}</div>}
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
                        <th>Phone</th>
                        <th>Balance</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((u) =>
                        editingId === u.id ? (
                          <tr key={u.id}>
                            <td>#{u.id}</td>
                            <td>
                              <input
                                id={`edit-name-${u.id}`}
                                className="inline-edit-input"
                                value={editForm.full_name}
                                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                              />
                              {editErrors.full_name && <div className="field-error">{editErrors.full_name}</div>}
                            </td>
                            <td>
                              <input
                                id={`edit-email-${u.id}`}
                                className="inline-edit-input"
                                value={editForm.email}
                                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                              />
                              {editErrors.email && <div className="field-error">{editErrors.email}</div>}
                            </td>
                            <td>
                              <input
                                id={`edit-phone-${u.id}`}
                                className="inline-edit-input"
                                value={editForm.phone_number}
                                onChange={(e) => setEditForm({ ...editForm, phone_number: e.target.value })}
                              />
                              {editErrors.phone_number && <div className="field-error">{editErrors.phone_number}</div>}
                            </td>
                            <td>
                              <input
                                id={`edit-balance-${u.id}`}
                                type="number"
                                className="inline-edit-input"
                                value={editForm.balance}
                                onChange={(e) => setEditForm({ ...editForm, balance: e.target.value })}
                              />
                              {editErrors.balance && <div className="field-error">{editErrors.balance}</div>}
                            </td>
                            <td>
                              <div className="row-actions">
                                <button className="icon-btn" onClick={() => saveEdit(u.id)}>
                                  Save
                                </button>
                                <button className="icon-btn" onClick={cancelEdit}>
                                  Cancel
                                </button>
                              </div>
                            </td>
                          </tr>
                        ) : (
                          <tr key={u.id}>
                            <td>#{u.id}</td>
                            <td>{u.full_name}</td>
                            <td>{u.email}</td>
                            <td>{u.phone_number}</td>
                            <td>Rs {Number(u.balance).toLocaleString()}</td>
                            <td>
                              <div className="row-actions">
                                <button className="icon-btn" onClick={() => startEdit(u)}>
                                  Edit
                                </button>
                                <button
                                  className="icon-btn danger"
                                  onClick={() => deleteUser(u.id, u.full_name)}
                                >
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      )}
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
                        <td>{t.sender_name} ({t.sender_phone})</td>
                        <td>{t.receiver_name} ({t.receiver_phone})</td>
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
                      <th>Amount</th>
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
                        <td>{f.amount ? `Rs ${Number(f.amount).toLocaleString()}` : "-"}</td>
                        <td>{f.model_score?.toFixed(4)}</td>
                        <td>{f.threshold}</td>
                        <td style={{ whiteSpace: "normal", fontFamily: "var(--font-body)" }}>{f.reason}</td>
                        <td>{new Date(f.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
        {tab === "disputes" && (
          <div className="card">
            <div className="card-title">Disputed transactions</div>
            {disputes.length === 0 ? (
              <div className="empty-state">No disputes yet.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Customer</th>
                      <th>Transaction</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {disputes.map((d) => (
                      <tr key={d.id}>
                        <td>#{d.id}</td>
                        <td>{d.customer_name} ({d.customer_phone})</td>
                        <td>
                          #{d.transaction_id} — {d.type}, Rs {Number(d.amount).toLocaleString()}
                          <br />
                          <span className="helper-text">score: {d.fraud_probability?.toFixed(4)}</span>
                        </td>
                        <td style={{ whiteSpace: "normal", fontFamily: "var(--font-body)" }}>
                          {d.customer_reason}
                        </td>
                        <td>
                          <span className={`dispute-status ${d.status}`}>{d.status}</span>
                        </td>
                        <td>
                          {d.status === "pending" ? (
                            <div className="row-actions">
                              <button className="icon-btn" onClick={() => resolveDispute(d.id, true)}>
                                Approve
                              </button>
                              <button className="icon-btn danger" onClick={() => resolveDispute(d.id, false)}>
                                Reject
                              </button>
                            </div>
                          ) : (
                            <span className="helper-text">{d.admin_notes || "—"}</span>
                          )}
                        </td>
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
