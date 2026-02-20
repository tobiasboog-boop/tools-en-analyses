"""Client configuration for Notifica's client (e.g., WVC).

This stores the general workflow/context for how the client organization
works with Syntess, processes werkbonnen, handles contracts, etc.

This is NOT about the end-clients (relaties) but about the main client
that Notifica serves (e.g., WVC as a whole).
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from .database import Base
from src.config import config


class ClientConfig(Base):
    """Configuration and context for Notifica's client organization.

    Stores general information about how the client works, which is used
    as context for LLM classification of werkbonnen.

    Example: WVC's general workflow, how they use Syntess, their conventions
    for werkbonnen, contract interpretation rules, etc.
    """
    __tablename__ = "client_config"
    __table_args__ = {"schema": config.DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Client identification
    client_code = Column(String(50), nullable=False, unique=True)  # e.g., "WVC"
    client_name = Column(String(255))  # e.g., "WVC Groep"

    # General workflow context for LLM
    # This is always included in classification prompts
    werkwijze = Column(Text)  # How they work with Syntess, werkbonnen, contracts

    # Optional: additional context sections
    syntess_context = Column(Text)  # Specific Syntess configuration/conventions
    werkbon_context = Column(Text)  # How werkbonnen are structured/processed
    contract_context = Column(Text)  # How contracts should be interpreted

    # Classificatie opdracht (de taak voor de LLM)
    classificatie_opdracht = Column(Text)  # What the LLM should do
    classificatie_output_format = Column(Text)  # Expected output format (JSON structure)

    # Status
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_full_context(self) -> str:
        """Get combined bedrijfscontext for LLM prompts."""
        parts = []

        if self.werkwijze:
            parts.append(f"## Algemene werkwijze {self.client_name or self.client_code}\n{self.werkwijze}")

        if self.syntess_context:
            parts.append(f"## Syntess configuratie\n{self.syntess_context}")

        if self.werkbon_context:
            parts.append(f"## Werkbon verwerking\n{self.werkbon_context}")

        if self.contract_context:
            parts.append(f"## Contract interpretatie\n{self.contract_context}")

        return "\n\n".join(parts) if parts else ""

    def get_system_prompt(self) -> str:
        """Get full system prompt: opdracht + output format + bedrijfscontext."""
        parts = []

        # 1. Classificatie opdracht (de taak)
        if self.classificatie_opdracht:
            parts.append(self.classificatie_opdracht)

        # 2. Output formaat
        if self.classificatie_output_format:
            parts.append(self.classificatie_output_format)

        # 3. Bedrijfscontext
        context = self.get_full_context()
        if context:
            parts.append(context)

        return "\n\n".join(parts) if parts else ""

    def to_dict(self):
        return {
            "id": self.id,
            "client_code": self.client_code,
            "client_name": self.client_name,
            "werkwijze": self.werkwijze,
            "syntess_context": self.syntess_context,
            "werkbon_context": self.werkbon_context,
            "contract_context": self.contract_context,
            "classificatie_opdracht": self.classificatie_opdracht,
            "classificatie_output_format": self.classificatie_output_format,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<ClientConfig {self.client_code}>"
