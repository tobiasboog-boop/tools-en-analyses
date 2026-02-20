from datetime import date

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_dwh_reader
from app.db.dwh_interface import DWHReader

router = APIRouter()


@router.get("/{klantnummer}/hoofdprojecten")
def get_hoofdprojecten(
    klantnummer: int = Path(...),
    dwh: DWHReader = Depends(get_dwh_reader),
):
    """Get all hoofdprojecten (top-level projects) from client DWH."""
    return dwh.get_hoofdprojecten(klantnummer)


@router.get("/{klantnummer}/deelprojecten/{hoofdproject_key}")
def get_deelprojecten(
    klantnummer: int = Path(...),
    hoofdproject_key: int = Path(...),
    dwh: DWHReader = Depends(get_dwh_reader),
):
    """Get deelprojecten (sub-projects) for a hoofdproject."""
    return dwh.get_deelprojecten(klantnummer, hoofdproject_key)


@router.get("/{klantnummer}/bestekparagrafen/{project_key}")
def get_bestekparagrafen(
    klantnummer: int = Path(...),
    project_key: int = Path(...),
    niveau: int = Query(1, ge=1, le=4),
    dwh: DWHReader = Depends(get_dwh_reader),
):
    """Get bestekparagrafen at specified level for a project."""
    return dwh.get_bestekparagrafen(klantnummer, project_key, niveau)


@router.get("/{klantnummer}/projectdata/{hoofdproject_key}")
def get_projectdata(
    klantnummer: int = Path(...),
    hoofdproject_key: int = Path(...),
    start_boekdatum: date | None = Query(None),
    einde_boekdatum: date | None = Query(None),
    dwh: DWHReader = Depends(get_dwh_reader),
):
    """Get full project data (costs, hours, requests) from DWH."""
    return dwh.get_projectdata(
        klantnummer=klantnummer,
        hoofdproject_key=hoofdproject_key,
        start_boekdatum=start_boekdatum,
        einde_boekdatum=einde_boekdatum,
    )
