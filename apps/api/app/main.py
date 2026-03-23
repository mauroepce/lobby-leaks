from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from .routers.search import router as search_router

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL not set")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = AsyncConnectionPool(DB_URL, min_size=1, max_size=5)
    async with pool:
        app.state.pool = pool
        yield


app = FastAPI(title="LobbyLeaks API", version="0.1.0", lifespan=lifespan)
app.include_router(search_router)
