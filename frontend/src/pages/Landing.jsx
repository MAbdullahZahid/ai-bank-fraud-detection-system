import { Link } from "react-router-dom";

export default function Landing() {
  return (
    <div className="page">
      <div className="container">
        <div className="hero">
          <div className="eyebrow">Real-time fraud scoring</div>
          <h1>Every transfer, checked before it settles.</h1>
          <p>
            An AI model scores every transaction the instant it's submitted —
            trained on millions of real transaction patterns to catch fraud
            without slowing down legitimate transfers.
          </p>
          <div className="hero-actions">
            <Link to="/login" className="btn" style={{ textDecoration: "none" }}>
              Customer login
            </Link>
            <Link to="/admin/login" className="btn-secondary" style={{ textDecoration: "none", padding: "14px 28px", borderRadius: 6 }}>
              Admin login
            </Link>
          </div>
        </div>

        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon">01</div>
            <h3>Instant scoring</h3>
            <p>
              Every transfer is passed through a trained XGBoost model the
              moment it's submitted — no waiting, no batch review.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">02</div>
            <h3>Phone-based transfers</h3>
            <p>
              Send money using just a destination phone number — like a
              mobile wallet. No public directory of other accounts.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">03</div>
            <h3>Admin oversight</h3>
            <p>
              Every flagged transaction is logged with a model confidence
              score and reason, visible to admins in real time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
