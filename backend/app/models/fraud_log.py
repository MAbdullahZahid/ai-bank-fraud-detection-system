from sqlalchemy import Column, Integer, Float, String,Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class FraudLog(Base):
    __tablename__ = "fraud_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    model_score = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
