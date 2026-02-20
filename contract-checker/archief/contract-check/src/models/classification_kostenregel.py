"""Classification results for individual kostenregels within a werkbon."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from .database import Base
from src.config import config


class ClassificationKostenregel(Base):
    """Classification result for a single kostenregel.

    Each werkbon classification can have multiple kostenregel classifications,
    allowing granular tracking of which costs are within/outside contract.
    """
    __tablename__ = "classification_kostenregels"
    __table_args__ = (
        CheckConstraint(
            "classificatie IN ('JA', 'NEE', 'ONZEKER')",
            name="valid_kostenregel_classificatie"
        ),
        {"schema": config.DB_SCHEMA}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Link to parent classification
    classification_id = Column(
        Integer,
        ForeignKey(f"{config.DB_SCHEMA}.classifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Reference to source data (optional, for traceability)
    kostenregel_key = Column(Integer, index=True)  # Key from financieel.Kosten
    werkbonparagraaf_key = Column(Integer)  # Parent paragraaf

    # Kostenregel details (snapshot at classification time)
    omschrijving = Column(Text)  # Voor arbeid inclusief medewerker/taak
    aantal = Column(Numeric(10, 2))
    verrekenprijs = Column(Numeric(10, 2))  # Totaalbedrag voor klant
    kostprijs = Column(Numeric(10, 2))  # Totaalbedrag intern (met dekking)
    categorie = Column(String(50))  # Arbeid, Materiaal, Overig, Materieel
    kostenbron = Column(String(100))  # Inkoop, Urenstaat, Materiaaluitgifte

    # Classification result
    classificatie = Column(String(20), nullable=False, index=True)  # JA, NEE, ONZEKER
    reden = Column(Text)  # Explanation for this specific line

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship back to parent
    classification = relationship("Classification", back_populates="kostenregels")

    def to_dict(self):
        return {
            "id": self.id,
            "classification_id": self.classification_id,
            "kostenregel_key": self.kostenregel_key,
            "werkbonparagraaf_key": self.werkbonparagraaf_key,
            "omschrijving": self.omschrijving,
            "aantal": float(self.aantal) if self.aantal else None,
            "verrekenprijs": float(self.verrekenprijs) if self.verrekenprijs else None,
            "kostprijs": float(self.kostprijs) if self.kostprijs else None,
            "categorie": self.categorie,
            "kostenbron": self.kostenbron,
            "classificatie": self.classificatie,
            "reden": self.reden,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<ClassificationKostenregel {self.id}: {self.classificatie}>"
