from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ModelFeedback(Base):
    __tablename__ = "model_feedback"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)

    original_probability = Column(Float, nullable=False)
    original_prediction = Column(String(20), nullable=False)
    corrected_label = Column(String(20), nullable=False)
    source = Column(String(30), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())