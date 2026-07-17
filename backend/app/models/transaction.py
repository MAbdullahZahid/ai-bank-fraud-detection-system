from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String(20), nullable=False)
    fraud_probability = Column(Float, nullable=True)
    prediction = Column(String(20), nullable=True)

    old_balance_orig = Column(Float, nullable=True)
    new_balance_orig = Column(Float, nullable=True)
    old_balance_dest = Column(Float, nullable=True)
    new_balance_dest = Column(Float, nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())