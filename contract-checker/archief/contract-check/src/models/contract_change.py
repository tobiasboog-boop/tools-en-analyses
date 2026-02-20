from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, ARRAY, Text
from .database import Base
from src.config import config


class ContractChange(Base):
    """Audit log for contract metadata changes."""
    __tablename__ = "contract_changes"
    __table_args__ = {"schema": config.DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey(f"{config.DB_SCHEMA}.contracts.id"))
    filename = Column(String(255), nullable=False)
    change_type = Column(String(20), nullable=False)  # INSERT, UPDATE, DEACTIVATE
    old_client_id = Column(String(50))
    new_client_id = Column(String(50))
    changed_fields = Column(ARRAY(Text))
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)
    changed_by = Column(String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "filename": self.filename,
            "change_type": self.change_type,
            "old_client_id": self.old_client_id,
            "new_client_id": self.new_client_id,
            "changed_fields": self.changed_fields,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "changed_by": self.changed_by,
        }
