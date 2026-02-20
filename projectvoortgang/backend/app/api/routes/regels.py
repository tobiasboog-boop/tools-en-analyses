from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.deps import get_dwh_reader, get_tenant, TenantContext
from app.db.app_db import get_db
from app.db.dwh_interface import DWHReader
from app.models.projectopname import Projectopname, Projectopnameregel
from app.schemas.regel import RegelBatchUpdate, RegelResponse
from app.services.opname_service import OpnameService

router = APIRouter()
opname_service = OpnameService()


@router.get("/{klantnummer}/{opname_key}/regels", response_model=list[RegelResponse])
def list_regels(
    opname_key: int = Path(...),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """List all regels for an opname."""
    regels = (
        db.query(Projectopnameregel)
        .filter(
            Projectopnameregel.projectopname_key == opname_key,
            Projectopnameregel.klantnummer == tenant.klantnummer,
        )
        .order_by(Projectopnameregel.bestekparagraaf)
        .all()
    )
    return regels


@router.post("/{klantnummer}/{opname_key}/regels/populate", response_model=list[RegelResponse])
def populate_regels(
    opname_key: int = Path(...),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    dwh: DWHReader = Depends(get_dwh_reader),
):
    """Populate opnameregels from DWH data based on opname settings."""
    opname = (
        db.query(Projectopname)
        .filter(
            Projectopname.projectopname_key == opname_key,
            Projectopname.klantnummer == tenant.klantnummer,
        )
        .first()
    )
    if not opname:
        raise HTTPException(status_code=404, detail="Opname niet gevonden")

    regels = opname_service.populate_regels(db, opname, dwh)
    return regels


@router.put("/{klantnummer}/{opname_key}/regels/batch")
def batch_update_regels(
    updates: RegelBatchUpdate,
    opname_key: int = Path(...),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """Batch update percentage_gereed values for multiple regels."""
    for update in updates.regels:
        regel = (
            db.query(Projectopnameregel)
            .filter(
                Projectopnameregel.regel_key == update.regel_key,
                Projectopnameregel.projectopname_key == opname_key,
                Projectopnameregel.klantnummer == tenant.klantnummer,
            )
            .first()
        )
        if regel:
            if update.percentage_gereed_inkoop is not None:
                regel.percentage_gereed_inkoop = update.percentage_gereed_inkoop
            if update.percentage_gereed_arbeid_montage is not None:
                regel.percentage_gereed_arbeid_montage = update.percentage_gereed_arbeid_montage
            if update.percentage_gereed_arbeid_projectgebonden is not None:
                regel.percentage_gereed_arbeid_projectgebonden = update.percentage_gereed_arbeid_projectgebonden

    db.commit()
    return {"status": "ok", "updated": len(updates.regels)}
