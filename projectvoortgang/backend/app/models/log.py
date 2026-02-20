from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.app_db import Base


class PALog(Base):
    __tablename__ = "nt_pa_log"
    __table_args__ = (
        Index("idx_pa_log_klant", "klantnummer"),
        Index("idx_pa_log_tijd", "tijdstip"),
        {"schema": "raas"},
    )

    log_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    klantnummer: Mapped[int] = mapped_column(Integer, nullable=False)
    tabel: Mapped[str] = mapped_column(String(100), nullable=False)
    record_key: Mapped[int | None] = mapped_column(Integer)
    actie: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB)
    gebruiker: Mapped[str] = mapped_column(String(100), default="system")
    tijdstip: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
