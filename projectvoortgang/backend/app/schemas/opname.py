from datetime import date, datetime

from pydantic import BaseModel, Field


class ProjectopnameCreate(BaseModel):
    hoofdproject_key: int
    hoofdproject: str | None = None
    hoogst_geselecteerd_projectniveau: int | None = None
    start_boekdatum: date | None = None
    einde_boekdatum: date | None = None
    grondslag_calculatie_kosten: str | None = None
    grondslag_geboekte_kosten: str | None = None
    groepering_paragraafniveau: int | None = None

    # Raw DWH aggregates (filled during creation from DWH data)
    calculatie_kostprijs_inkoop: float = 0
    calculatie_kostprijs_arbeid_montage: float = 0
    calculatie_kostprijs_arbeid_projectgebonden: float = 0
    calculatie_verrekenprijs_inkoop: float = 0
    calculatie_verrekenprijs_arbeid_montage: float = 0
    calculatie_verrekenprijs_arbeid_projectgebonden: float = 0
    calculatie_montage_uren: float = 0
    calculatie_projectgebonden_uren: float = 0
    definitieve_kostprijs_inkoop: float = 0
    definitieve_kostprijs_arbeid_montage: float = 0
    definitieve_kostprijs_arbeid_projectgebonden: float = 0
    definitieve_verrekenprijs_inkoop: float = 0
    definitieve_verrekenprijs_arbeid_montage: float = 0
    definitieve_verrekenprijs_arbeid_projectgebonden: float = 0
    onverwerkte_verrekenprijs_inkoop: float = 0
    onverwerkte_verrekenprijs_arbeid_montage: float = 0
    onverwerkte_verrekenprijs_arbeid_projectgebonden: float = 0
    montage_uren_definitief: float = 0
    montage_uren_onverwerkt: float = 0
    projectgebonden_uren_definitief: float = 0
    projectgebonden_uren_onverwerkt: float = 0
    historische_verzoeken_inkoop: float = 0
    historische_verzoeken_montage: float = 0
    historische_verzoeken_projectgebonden: float = 0
    historische_verzoeken_montage_uren: float = 0
    historische_verzoeken_projectgebonden_uren: float = 0


class ProjectopnameUpdate(BaseModel):
    hoofdproject: str | None = None
    start_boekdatum: date | None = None
    einde_boekdatum: date | None = None
    grondslag_calculatie_kosten: str | None = None
    grondslag_geboekte_kosten: str | None = None
    groepering_paragraafniveau: int | None = None
    opmerking: str | None = None


class ProjectopnameResponse(BaseModel):
    projectopname_key: int
    klantnummer: int
    hoofdproject_key: int
    hoofdproject: str | None
    hoogst_geselecteerd_projectniveau: int | None
    start_boekdatum: date | None
    einde_boekdatum: date | None
    grondslag_calculatie_kosten: str | None
    grondslag_geboekte_kosten: str | None
    groepering_paragraafniveau: int | None

    # Resolved values
    calculatie_inkoop: float
    calculatie_montage: float
    calculatie_projectgebonden: float
    geboekt_inkoop: float
    geboekt_montage: float
    geboekt_projectgebonden: float
    geboekt_montage_uren: float
    geboekt_projectgebonden_uren: float

    # Calculated
    tmb_inkoop: float
    tmb_montage: float
    tmb_projectgebonden: float
    tmb_montage_uren: float
    tmb_projectgebonden_uren: float

    verschil_inkoop_huidige_stand: float
    verschil_montage_huidige_stand: float
    verschil_projectgebonden_huidige_stand: float

    gemiddeld_pg_inkoop: float
    gemiddeld_pg_montage: float
    gemiddeld_pg_projectgebonden: float
    gemiddeld_pg_totaal: float

    verschil_inkoop_einde_project: float
    verschil_montage_einde_project: float
    verschil_projectgebonden_einde_project: float

    ondergrens_inkoop: float
    ondergrens_montage: float
    ondergrens_projectgebonden: float
    bovengrens_inkoop: float
    bovengrens_montage: float
    bovengrens_projectgebonden: float

    # Historical requests
    historische_verzoeken_inkoop: float
    historische_verzoeken_montage: float
    historische_verzoeken_projectgebonden: float

    # Status
    autorisatie_status: str
    opgeslagen: bool
    opmerking: str | None

    # Audit
    aanmaakdatum: datetime
    aanmaker: str
    wijzigdatum: datetime
    wijziger: str

    model_config = {"from_attributes": True}
