from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import berekeningen, dwh, health, opnames, regels
from app.config import settings

app = FastAPI(
    title="Projectvoortgang Opname API",
    description="Multi-tenant projectvoortgang opname applicatie",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(dwh.router, prefix="/api/dwh", tags=["dwh"])
app.include_router(opnames.router, prefix="/api/opnames", tags=["opnames"])
app.include_router(regels.router, prefix="/api/opnames", tags=["regels"])
app.include_router(berekeningen.router, prefix="/api/opnames", tags=["berekeningen"])
