from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import AsyncConnectionPool

from .routers.graph import router as graph_router
from .routers.search import router as search_router

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL not set")

# Allowed origins for CORS. Defaults cover local Next dev on :3000 plus a
# preview port; production origins come from `CORS_ORIGINS` (comma-separated)
# so deployment doesn't need a code change to add a new domain.
_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = AsyncConnectionPool(DB_URL, min_size=1, max_size=5)
    async with pool:
        app.state.pool = pool
        yield


app = FastAPI(title="LobbyLeaks API", version="0.1.0", lifespan=lifespan)

# The public read endpoints (/search, /graph) need browser access from the
# frontend; this middleware reflects the Origin only when it's on the
# allow-list so we don't accidentally publish a wildcard CORS surface.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["X-Tenant-Id"],
)

app.include_router(search_router)
app.include_router(graph_router)
