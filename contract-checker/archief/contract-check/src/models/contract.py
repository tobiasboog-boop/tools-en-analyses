from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, UniqueConstraint
)
from .database import Base
from src.config import config


class Contract(Base):
    """Contract met LLM conversie tekst.

    Klant koppelingen worden beheerd via de contract_relatie tabel (één-op-veel).

    Flow:
    1. Conversie: Excel/Word wordt omgezet naar tekst, opgeslagen hier
    2. Register: Klanten worden gekoppeld via contract_relatie tabel
    3. Classificatie: Tekst wordt gebruikt om werkbonnen te classificeren
    """
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("filename", name="contracts_filename_key"),
        {"schema": config.DB_SCHEMA}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # LLM conversie
    filename = Column(String(255), nullable=False, index=True)  # bijv. "Thuisvester.txt"
    content = Column(Text)  # De LLM conversie tekst

    # Bron bestand
    source_file = Column(String(255))  # bijv. "Contractvoorwaarden diverse WBV.xlsx"
    source_sheet = Column(String(255))  # bijv. "Thuisvester"

    # LLM interpretatie context per contract
    # Instructies voor de LLM over hoe dit specifieke contract te begrijpen/gebruiken
    # Bijv: "Dit is een all-in tarief", "Staffelkorting bij >10 werkbonnen", etc.
    llm_context = Column(Text)

    # LLM-ready versie van het contract
    # Verbeterde versie gegenereerd door LLM op basis van content + llm_context
    # Eventueel verrijkt met inzichten uit historische werkbonnen
    llm_ready = Column(Text)

    # Status
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "content": self.content,
            "source_file": self.source_file,
            "source_sheet": self.source_sheet,
            "llm_context": self.llm_context,
            "llm_ready": self.llm_ready,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Contract {self.filename}>"
