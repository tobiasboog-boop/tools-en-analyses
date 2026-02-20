from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.deps import get_tenant, TenantContext
from app.db.app_db import get_db
from app.models.projectopname import Projectopname, Projectopnameregel
from app.schemas.opname import ProjectopnameResponse
from app.services.calculation_service import CalculationService

router = APIRouter()
calc_service = CalculationService()


@router.post("/{klantnummer}/{opname_key}/bereken", response_model=ProjectopnameResponse)
def bereken_opname(
    opname_key: int = Path(...),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """Run full recalculation for an opname."""
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

    regels = (
        db.query(Projectopnameregel)
        .filter(Projectopnameregel.projectopname_key == opname_key)
        .all()
    )

    calc_service.recalculate_all(opname, regels)
    opname.wijziger = tenant.user_id
    db.commit()
    db.refresh(opname)
    return opname


@router.post("/{klantnummer}/{opname_key}/opslaan", response_model=ProjectopnameResponse)
def opslaan_opname(
    opname_key: int = Path(...),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """Save and calculate an opname. Sets opgeslagen=True."""
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

    regels = (
        db.query(Projectopnameregel)
        .filter(Projectopnameregel.projectopname_key == opname_key)
        .all()
    )

    calc_service.recalculate_all(opname, regels)
    opname.opgeslagen = True
    opname.wijziger = tenant.user_id
    db.commit()
    db.refresh(opname)
    return opname
