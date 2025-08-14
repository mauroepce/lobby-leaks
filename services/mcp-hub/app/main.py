# services/mcp-hub/app/main.py
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from psycopg_pool import AsyncConnectionPool

from .middleware import TenantHeaderMiddleware   # <─ usamos el middleware externo

load_dotenv()  # solo en local
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL not set")

# Pool global (psycopg3)
pool = AsyncConnectionPool(DB_URL, min_size=1, max_size=5)

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with pool:   # abre pool al arrancar
        yield          # app viva
    # pool se cierra solo al apagar

app = FastAPI(title="LobbyLeaks MCP Stub", lifespan=lifespan)

# Hacer el pool accesible al middleware
app.state.pool = pool

# Registrar el middleware de tenant
app.add_middleware(TenantHeaderMiddleware)

# ───── JSON-RPC stub
STUBS = {"fetch_pdf", "ocr_pdf", "summarise_doc", "entity_link"}

@app.post("/rpc2")
async def rpc2(req: Request):
    method = (await req.json()).get("method", "")
    if method in STUBS:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"{method} not implemented yet"
        )
    raise HTTPException(status_code=400, detail="Unknown method")
