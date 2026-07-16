export default function StampBadge({ result }) {
  if (!result) return null;

  const isFraud = result.prediction === "fraud";

  return (
    <div className="stamp-wrap">
      <div className={`stamp ${isFraud ? "fraud" : "legit"}`}>
        {isFraud ? "Flagged" : "Approved"}
      </div>
      <div className="stamp-meta">
        Model confidence: <strong>{(result.fraud_probability * 100).toFixed(2)}%</strong>
        <br />
        Transaction #{result.id} · {result.type} · Rs {Number(result.amount).toLocaleString()}
      </div>
    </div>
  );
}
