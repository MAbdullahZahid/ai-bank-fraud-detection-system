import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

export default function AdminLogin() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      // FastAPI's OAuth2PasswordRequestForm expects form-urlencoded, not JSON
      const body = new URLSearchParams();
      body.append("username", username);
      body.append("password", password);

      const res = await api.post("/api/auth/login", body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      localStorage.setItem("admin_token", res.data.access_token);
      navigate("/admin/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed. Check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 420 }}>
        <div className="eyebrow">Admin access</div>
        <h1 className="page-title">Sign in</h1>
        <p className="page-subtitle">
          Manage accounts and monitor every transaction the fraud model has scored.
        </p>

        <div className="card">
          {error && <div className="error-banner">{error}</div>}
          <form onSubmit={submit}>
            <div className="field">
              <label>Username</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
            </div>
            <div className="field">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <button className="btn" type="submit" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
