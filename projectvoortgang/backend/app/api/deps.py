from dataclasses import dataclass

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.config import settings
from app.db.app_db import get_db
from app.db.dwh_interface import DWHReader
from app.db.dwh_connection import PostgresDWHReader


@dataclass
class TenantContext:
    klantnummer: int
    user_id: str = "dev-user"
    user_name: str = "Development User"


async def get_current_user() -> dict:
    """Auth hook - hardcoded for now. Will be replaced with core app JWT validation."""
    return {"user_id": "dev-user", "name": "Development User"}


async def get_tenant(klantnummer: int = Path(...)) -> TenantContext:
    """Validates klantnummer and returns tenant context."""
    return TenantContext(klantnummer=klantnummer)


def get_dwh_reader(klantnummer: int = Path(...)) -> DWHReader:
    """Returns DWH reader for tenant. Now: direct PG. Later: Core App API."""
    return PostgresDWHReader(
        host=settings.dwh_host,
        port=settings.dwh_port,
        database=str(klantnummer),
        user=settings.dwh_user,
        password=settings.dwh_password,
    )
