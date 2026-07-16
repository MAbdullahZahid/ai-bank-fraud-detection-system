export default function StampBadge({ result }) {
  if (!result) return null;

  const isFraud = result.prediction === "fraud";
  const isIncoming = result.type === "CASH_IN";

  let headline = "Approved";
  let detail = "Money moved successfully";
  if (isFraud) {
    headline = "Blocked";
    detail = "No funds moved";
  } else if (isIncoming) {
    headline = "Received";
    detail = "Money entered the customer account";
  }

  return (
    <div className="stamp-wrap">
      <div className={`stamp ${isFraud ? "fraud" : "legit"}`}>
        {headline}
      </div>
      <div className="stamp-meta">
        Model confidence: <strong>{(result.fraud_probability * 100).toFixed(2)}%</strong>
        <br />
        {detail}
        <br />
        Transaction #{result.id} · {result.type} · Rs {Number(result.amount).toLocaleString()}
      </div>
    </div>
  );
}
