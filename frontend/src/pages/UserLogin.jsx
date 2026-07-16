import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

export default function UserLogin() {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const validate = () => {
    const errs = {};
    if (!phone.trim()) {
      errs.phone = "Phone number is required.";
    } else if (!/^\+?[0-9]{7,15}$/.test(phone.trim())) {
      errs.phone = "Enter a valid phone number (7-15 digits).";
    }
    if (!password) {
      errs.password = "Password is required.";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const submit = async (e) => {
    e.preventDefault();
    setApiError("");
    if (!validate()) return;

    setLoading(true);
    try {
      const res = await api.post("/api/auth/user-login", {
        phone_number: phone.trim(),
        password,
      });
      localStorage.setItem("user_token", res.data.access_token);
      navigate("/transfer");
    } catch (err) {
      setApiError(err.response?.data?.detail || "Login failed. Check your phone number and password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 420 }}>
        <div className="eyebrow">Customer access</div>
        <h1 className="page-title">Sign in</h1>
        <p className="page-subtitle">
          Use the phone number and password your admin set up for your account.
        </p>

        <div className="card">
          {apiError && <div className="error-banner">{apiError}</div>}
          <form onSubmit={submit} noValidate>
            <div className={`field ${errors.phone ? "has-error" : ""}`}>
              <label>Phone number</label>
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="e.g. 03001234567"
                autoFocus
              />
              {errors.phone && <div className="field-error">{errors.phone}</div>}
            </div>
            <div className={`field ${errors.password ? "has-error" : ""}`}>
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {errors.password && <div className="field-error">{errors.password}</div>}
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
