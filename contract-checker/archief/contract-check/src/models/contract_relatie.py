"""Many-to-many relationship between contracts and relaties (clients)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from .database import Base
from src.config import config


class ContractRelatie(Base):
    """Links a contract to one or more relaties (clients).

    A contract can apply to multiple relaties, and a relatie can have
    multiple contracts.
    """
    __tablename__ = "contract_relatie"
    __table_args__ = (
        UniqueConstraint("contract_id", "client_id", name="uq_contract_relatie"),
        {"schema": config.DB_SCHEMA}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Reference to contract (no FK constraint for flexibility)
    contract_id = Column(Integer, nullable=False, index=True)

    # Relatie (client) from stam.Relaties - we store the code, not FK since different DB
    client_id = Column(String(50), nullable=False, index=True)
    client_name = Column(String(255))  # Cached for display

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100))  # Who made this link

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "client_id": self.client_id,
            "client_name": self.client_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }

    def __repr__(self):
        return f"<ContractRelatie contract={self.contract_id} -> {self.client_id}>"
