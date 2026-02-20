from pydantic import BaseModel, Field


class RegelResponse(BaseModel):
    regel_key: int
    projectopname_key: int
    klantnummer: int

    project_key: int | None
    project: str | None
    projectniveau: int | None
    projectfase: str | None
    deelproject_jn: str

    bestekparagraaf_key: int | None
    bestekparagraaf: str | None
    bestekparagraafniveau: int | None

    # Budget
    calculatie_kosten_inkoop: float
    calculatie_kosten_arbeid_montage: float
    calculatie_kosten_arbeid_projectgebonden: float
    calculatie_montage_uren: float
    calculatie_projectgebonden_uren: float

    # Realized
    geboekte_kosten_inkoop: float
    geboekte_kosten_arbeid_montage: float
    geboekte_kosten_arbeid_projectgebonden: float
    montage_uren: float
    projectgebonden_uren: float

    # Previous PG
    laatste_pg_inkoop: float | None
    laatste_pg_montage: float | None
    laatste_pg_projectgebonden: float | None

    # User input
    percentage_gereed_inkoop: float
    percentage_gereed_arbeid_montage: float
    percentage_gereed_arbeid_projectgebonden: float

    model_config = {"from_attributes": True}


class RegelUpdate(BaseModel):
    regel_key: int
    percentage_gereed_inkoop: float | None = None
    percentage_gereed_arbeid_montage: float | None = None
    percentage_gereed_arbeid_projectgebonden: float | None = None


class RegelBatchUpdate(BaseModel):
    regels: list[RegelUpdate]
