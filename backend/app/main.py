from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.doc import router as doc_router
from app.api.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Future: run Alembic migrations, warm up pools, etc.
    yield


app = FastAPI(
    title="KNIME Doc Generator",
    version="0.1.0",
    description="Upload a KNIME .knwf workflow and get generated documentation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(doc_router, prefix="/api")
