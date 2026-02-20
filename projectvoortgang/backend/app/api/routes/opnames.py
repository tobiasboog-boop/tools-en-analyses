from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.deps import get_tenant, TenantContext
from app.db.app_db import get_db
from app.models.projectopname import Projectopname
from app.schemas.opname import (
    ProjectopnameCreate,
    ProjectopnameResponse,
    ProjectopnameUpdate,
)

router = APIRouter()


@router.get("/{klantnummer}", response_model=list[ProjectopnameResponse])
def list_opnames(
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """List all opnames for a tenant."""
    opnames = (
        db.query(Projectopname)
        .filter(Projectopname.klantnummer == tenant.klantnummer)
        .order_by(Projectopname.aanmaakdatum.desc())
        .all()
    )
    return opnames


@router.get("/{klantnummer}/{opname_key}", response_model=ProjectopnameResponse)
def get_opname(
    opname_key: int = Path(...),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """Get a single opname with its regels."""
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
    return opname


@router.post("/{klantnummer}", response_model=ProjectopnameResponse, status_code=201)
def create_opname(
    data: ProjectopnameCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """Create a new opname header."""
    opname = Projectopname(
        klantnummer=tenant.klantnummer,
        aanmaker=tenant.user_id,
        wijziger=tenant.user_id,
        **data.model_dump(),
    )
    db.add(opname)
    db.commit()
    db.refresh(opname)
    return opname


@router.put("/{klantnummer}/{opname_key}", response_model=ProjectopnameResponse)
def update_opname(
    data: ProjectopnameUpdate,
    opname_key: int = Path(...),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """Update an opname header."""
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

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(opname, field, value)
    opname.wijziger = tenant.user_id

    db.commit()
    db.refresh(opname)
    return opname


@router.delete("/{klantnummer}/{opname_key}", status_code=204)
def delete_opname(
    opname_key: int = Path(...),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """Delete an opname (only if status is Concept)."""
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
    if opname.autorisatie_status != "Concept":
        raise HTTPException(status_code=400, detail="Kan alleen concept-opnames verwijderen")

    db.delete(opname)
    db.commit()
