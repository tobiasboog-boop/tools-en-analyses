from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.app_db import Base


class Projectopname(Base):
    __tablename__ = "nt_projectopname"
    __table_args__ = (
        Index("idx_projectopname_klant", "klantnummer"),
        Index("idx_projectopname_project", "hoofdproject_key"),
        {"schema": "raas"},
    )

    projectopname_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    klantnummer: Mapped[int] = mapped_column(Integer, nullable=False)

    # Project reference (from DWH)
    hoofdproject_key: Mapped[int] = mapped_column(Integer, nullable=False)
    hoofdproject: Mapped[str | None] = mapped_column(String(250))
    hoogst_geselecteerd_projectniveau: Mapped[int | None] = mapped_column(Integer)

    # Period
    start_boekdatum: Mapped[date | None] = mapped_column(Date)
    einde_boekdatum: Mapped[date | None] = mapped_column(Date)

    # Settings
    grondslag_calculatie_kosten: Mapped[str | None] = mapped_column(String(150))
    grondslag_geboekte_kosten: Mapped[str | None] = mapped_column(String(150))
    groepering_paragraafniveau: Mapped[int | None] = mapped_column(Integer)

    # --- Raw DWH aggregates: Calculatie kostprijzen ---
    calculatie_kostprijs_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_kostprijs_arbeid_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_kostprijs_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Raw DWH aggregates: Calculatie verrekenprijzen ---
    calculatie_verrekenprijs_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_verrekenprijs_arbeid_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_verrekenprijs_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Raw DWH aggregates: Calculatie uren ---
    calculatie_montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Raw DWH aggregates: Definitieve kostprijzen ---
    definitieve_kostprijs_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    definitieve_kostprijs_arbeid_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    definitieve_kostprijs_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Raw DWH aggregates: Definitieve verrekenprijzen ---
    definitieve_verrekenprijs_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    definitieve_verrekenprijs_arbeid_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    definitieve_verrekenprijs_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Raw DWH aggregates: Onverwerkte verrekenprijzen ---
    onverwerkte_verrekenprijs_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    onverwerkte_verrekenprijs_arbeid_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    onverwerkte_verrekenprijs_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Raw DWH aggregates: Gerealiseerde uren ---
    montage_uren_definitief: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    montage_uren_onverwerkt: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    projectgebonden_uren_definitief: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    projectgebonden_uren_onverwerkt: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Raw DWH aggregates: Historische verzoeken ---
    historische_verzoeken_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    historische_verzoeken_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    historische_verzoeken_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    historische_verzoeken_montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    historische_verzoeken_projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Resolved: Calculatie (based on grondslag selection) ---
    calculatie_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Resolved: Geboekt (based on grondslag selection) ---
    geboekt_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    geboekt_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    geboekt_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    geboekt_montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    geboekt_projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Calculated: TMB (Te Mogen Besteden) ---
    tmb_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    tmb_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    tmb_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    tmb_montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    tmb_projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Calculated: Verschil huidige stand ---
    verschil_inkoop_huidige_stand: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verschil_montage_huidige_stand: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verschil_projectgebonden_huidige_stand: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verschil_montage_uren_huidige_stand: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verschil_projectgebonden_uren_huidige_stand: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Calculated: Gemiddeld PG ---
    gemiddeld_pg_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    gemiddeld_pg_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    gemiddeld_pg_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    gemiddeld_pg_totaal: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Calculated: Verschil einde project ---
    verschil_inkoop_einde_project: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verschil_montage_einde_project: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verschil_projectgebonden_einde_project: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verschil_montage_uren_einde_project: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verschil_projectgebonden_uren_einde_project: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Calculated: Grenzen ---
    ondergrens_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    ondergrens_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    ondergrens_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    ondergrens_montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    ondergrens_projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    bovengrens_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    bovengrens_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    bovengrens_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    bovengrens_montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    bovengrens_projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # --- Status ---
    autorisatie_status: Mapped[str] = mapped_column(String(18), default="Concept")
    autorisatie_datum: Mapped[datetime | None] = mapped_column(DateTime)
    autoriseerder: Mapped[str | None] = mapped_column(String(150))
    opgeslagen: Mapped[bool] = mapped_column(Boolean, default=False)
    opmerking: Mapped[str | None] = mapped_column(Text)

    # --- Audit ---
    aanmaakdatum: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    aanmaker: Mapped[str] = mapped_column(String(100), default="system")
    wijzigdatum: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    wijziger: Mapped[str] = mapped_column(String(100), default="system")

    # Relationship
    regels: Mapped[list["Projectopnameregel"]] = relationship(
        back_populates="opname", cascade="all, delete-orphan"
    )


class Projectopnameregel(Base):
    __tablename__ = "nt_projectopnameregels"
    __table_args__ = (
        Index("idx_opnameregel_opname", "projectopname_key"),
        Index("idx_opnameregel_klant", "klantnummer"),
        CheckConstraint("percentage_gereed_inkoop BETWEEN 0 AND 100"),
        CheckConstraint("percentage_gereed_arbeid_montage BETWEEN 0 AND 100"),
        CheckConstraint("percentage_gereed_arbeid_projectgebonden BETWEEN 0 AND 100"),
        {"schema": "raas"},
    )

    regel_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projectopname_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("raas.nt_projectopname.projectopname_key", ondelete="CASCADE"), nullable=False
    )
    klantnummer: Mapped[int] = mapped_column(Integer, nullable=False)

    # What this line represents
    project_key: Mapped[int | None] = mapped_column(Integer)
    project: Mapped[str | None] = mapped_column(String(250))
    projectniveau: Mapped[int | None] = mapped_column(Integer)
    projectfase: Mapped[str | None] = mapped_column(String(250))
    deelproject_jn: Mapped[str] = mapped_column(String(1), default="N")

    # Bestekparagraaf (when deelproject_jn = 'N')
    bestekparagraaf_key: Mapped[int | None] = mapped_column(Integer)
    bestekparagraaf: Mapped[str | None] = mapped_column(String(250))
    bestekparagraafniveau: Mapped[int | None] = mapped_column(Integer)

    # Calculatie kosten (budget) per category
    calculatie_kosten_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_kosten_arbeid_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_kosten_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # Calculatie kostprijzen (for weighted average)
    calculatie_kostprijs_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_kostprijs_arbeid_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    calculatie_kostprijs_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # Geboekte kosten (realized) per category
    geboekte_kosten_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    geboekte_kosten_arbeid_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    geboekte_kosten_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # Historische verzoeken per category
    verzoeken_inkoop: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verzoeken_montage: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verzoeken_projectgebonden: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verzoeken_montage_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    verzoeken_projectgebonden_uren: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # Laatste PG van vorige opname (voor vergelijking)
    laatste_pg_inkoop: Mapped[float | None] = mapped_column(Numeric(5, 2))
    laatste_pg_montage: Mapped[float | None] = mapped_column(Numeric(5, 2))
    laatste_pg_projectgebonden: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # USER INPUT: percentage gereed per category (0-100)
    percentage_gereed_inkoop: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    percentage_gereed_arbeid_montage: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    percentage_gereed_arbeid_projectgebonden: Mapped[float] = mapped_column(Numeric(5, 2), default=0)

    # Relationship
    opname: Mapped["Projectopname"] = relationship(back_populates="regels")
