from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.models import DrugLabel
from app.routers import drugs


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="OpenFDA Drug Integration API",
    version="1.0.0",
    description="API para extração, persistência e consulta de bulas de medicamentos via OpenFDA.",
    lifespan=lifespan,
)

app.include_router(drugs.router)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
