import { useEffect } from "react";
import { Link } from "react-router-dom";

const CARDS = [
  {
    code: "01",
    title: "Customer console",
    text: "See profile, balance, and transaction history after login.",
  },
  {
    code: "02",
    title: "Scenario cards",
    text: "Pick a bank flow and get the right counterparty phone for easy testing.",
  },
  {
    code: "03",
    title: "Fraud feedback",
    text: "Blocked fraud, received cash-in, and legitimate transfers are labeled clearly.",
  },
];

const SCENARIOS = [
  ["TRANSFER", "Customer to customer", "Direct person-to-person money movement."],
  ["CASH_OUT", "ATM style", "Withdrawal-style testing with an ATM or agent counterparty."],
  ["PAYMENT", "Merchant", "Simulate paying a store or merchant account."],
  ["CASH_IN", "Deposit", "Money enters the account and should display as received."],
  ["DEBIT", "Automatic", "Use this for bank deductions, utility bills, or scheduled charges."],
  ["ADMIN", "Monitoring", "Track flagged transactions and review fraud logs from the admin dashboard."],
];

export default function Landing() {
  useEffect(() => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("user_token");
  }, []);

  return (
    <div className="page">
      <div className="container bank-shell">
        <section className="hero">
          <div className="eyebrow">Real-time fraud scoring</div>
          <h1>Bank-style scenario testing with fraud checks built in.</h1>
          <p>
            Test transfer, cash out, payment, cash in, and debit flows from a clean customer console.
            Fraudulent cases are blocked, received cash-in is shown clearly, and the admin portal stays in sync.
          </p>
          <div className="hero-actions">
            <Link to="/login" className="btn" style={{ textDecoration: "none" }}>
              Customer login
            </Link>
            <Link
              to="/admin/login"
              className="btn-secondary"
              style={{ textDecoration: "none", padding: "14px 28px", borderRadius: 6 }}
            >
              Admin login
            </Link>
          </div>
        </section>

        <section className="feature-grid">
          {CARDS.map((card) => (
            <article className="feature-card" key={card.code}>
              <div className="feature-icon">{card.code}</div>
              <h3>{card.title}</h3>
              <p>{card.text}</p>
            </article>
          ))}
        </section>

        <section className="scenario-grid">
          {SCENARIOS.map(([title, subtitle, text]) => (
            <article className="scenario-card" key={title}>
              <div className="scenario-card-head">
                <span>{title}</span>
                <span>{subtitle}</span>
              </div>
              <p>{text}</p>
            </article>
          ))}
        </section>
      </div>
    </div>
  );
}
