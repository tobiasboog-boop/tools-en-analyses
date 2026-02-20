from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, CheckConstraint
from sqlalchemy.orm import relationship
from .database import Base
from src.config import config


class Classification(Base):
    """Classification results for werkbonnen.

    Twee modi:
    - validatie: historische werkbon, werkelijke_classificatie wordt direct ingevuld
    - classificatie: openstaande werkbon, werkelijke_classificatie later (retroactief)

    Classificatie kan nu ook GEDEELTELIJK zijn wanneer sommige kostenregels
    binnen contract vallen en andere niet.
    """
    __tablename__ = "classifications"
    __table_args__ = (
        CheckConstraint("classificatie IN ('JA', 'NEE', 'ONZEKER', 'GEDEELTELIJK')", name="valid_classificatie"),
        CheckConstraint("modus IN ('validatie', 'classificatie')", name="valid_modus"),
        {"schema": config.DB_SCHEMA}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    werkbon_id = Column(String(50), nullable=False, index=True)
    hoofdwerkbon_key = Column(Integer, index=True)  # Link naar datawarehouse voor retroactieve validatie
    modus = Column(String(20), nullable=False, default="classificatie", index=True)  # validatie of classificatie
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    classificatie = Column(String(20), nullable=False, index=True)  # JA, NEE, ONZEKER, GEDEELTELIJK
    mapping_score = Column(Numeric(3, 2))
    contract_referentie = Column(Text)  # Verwijzing naar relevant contract artikel(en)
    toelichting = Column(Text)
    werkbon_bedrag = Column(Numeric(10, 2))
    werkelijke_classificatie = Column(String(20))  # Bij validatie direct, bij classificatie later
    contract_filename = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to kostenregel-level classifications
    kostenregels = relationship(
        "ClassificationKostenregel",
        back_populates="classification",
        cascade="all, delete-orphan"
    )

    def to_dict(self, include_kostenregels: bool = False):
        result = {
            "id": self.id,
            "werkbon_id": self.werkbon_id,
            "hoofdwerkbon_key": self.hoofdwerkbon_key,
            "modus": self.modus,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "classificatie": self.classificatie,
            "mapping_score": float(self.mapping_score) if self.mapping_score else None,
            "contract_referentie": self.contract_referentie,
            "toelichting": self.toelichting,
            "werkbon_bedrag": float(self.werkbon_bedrag) if self.werkbon_bedrag else None,
            "werkelijke_classificatie": self.werkelijke_classificatie,
            "contract_filename": self.contract_filename,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_kostenregels and self.kostenregels:
            result["kostenregels"] = [kr.to_dict() for kr in self.kostenregels]
        return result
