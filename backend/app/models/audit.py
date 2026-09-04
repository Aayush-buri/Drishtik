from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    target_identifier = Column(String(100), nullable=True, index=True)
    details = Column(String(2000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", backref="audit_logs")
    user = relationship("User")
