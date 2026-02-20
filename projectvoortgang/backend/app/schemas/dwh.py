from datetime import date

from pydantic import BaseModel


class DWHHoofdproject(BaseModel):
    project_key: int
    project_naam: str
    projectfase: str | None = None
    projectniveau: int = 1
    start_boekdatum: date | None = None
    einde_boekdatum: date | None = None


class DWHDeelproject(BaseModel):
    project_key: int
    project_naam: str
    projectfase: str | None = None
    projectniveau: int
    hoofdproject_key: int


class DWHBestekparagraaf(BaseModel):
    bestekparagraaf_key: int
    bestekparagraaf: str
    bestekparagraafniveau: int


class DWHProjectdata(BaseModel):
    """Full project data row from DWH - one per bestekparagraaf/deelproject."""

    project_key: int
    project_naam: str | None = None
    projectniveau: int | None = None
    projectfase: str | None = None
    bestekparagraaf_key: int | None = None
    bestekparagraaf: str | None = None
    bestekparagraafniveau: int | None = None

    # Calculatie kostprijzen
    calculatie_kostprijs_inkoop: float = 0
    calculatie_kostprijs_arbeid_montage: float = 0
    calculatie_kostprijs_arbeid_projectgebonden: float = 0

    # Calculatie verrekenprijzen
    calculatie_verrekenprijs_inkoop: float = 0
    calculatie_verrekenprijs_arbeid_montage: float = 0
    calculatie_verrekenprijs_arbeid_projectgebonden: float = 0

    # Calculatie uren
    calculatie_montage_uren: float = 0
    calculatie_projectgebonden_uren: float = 0

    # Definitieve kostprijzen
    definitieve_kostprijs_inkoop: float = 0
    definitieve_kostprijs_arbeid_montage: float = 0
    definitieve_kostprijs_arbeid_projectgebonden: float = 0

    # Definitieve verrekenprijzen
    definitieve_verrekenprijs_inkoop: float = 0
    definitieve_verrekenprijs_arbeid_montage: float = 0
    definitieve_verrekenprijs_arbeid_projectgebonden: float = 0

    # Onverwerkte verrekenprijzen
    onverwerkte_verrekenprijs_inkoop: float = 0
    onverwerkte_verrekenprijs_arbeid_montage: float = 0
    onverwerkte_verrekenprijs_arbeid_projectgebonden: float = 0

    # Gerealiseerde uren
    montage_uren_definitief: float = 0
    montage_uren_onverwerkt: float = 0
    projectgebonden_uren_definitief: float = 0
    projectgebonden_uren_onverwerkt: float = 0

    # Historische verzoeken
    historische_verzoeken_inkoop: float = 0
    historische_verzoeken_montage: float = 0
    historische_verzoeken_projectgebonden: float = 0
    historische_verzoeken_montage_uren: float = 0
    historische_verzoeken_projectgebonden_uren: float = 0
