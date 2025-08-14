# services/mcp-hub/app/middleware.py
import re
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from psycopg_pool import AsyncConnectionPool

TENANT_RE = re.compile(r"^[A-Z]{2}$")   # CL, UY, ...
GUC_NAME = "app.current_tenant"         # nombre de la GUC

class TenantHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # 1) validar header (no lances HTTPException desde middleware; devuelve 400)
        tenant = (request.headers.get("X-Tenant-Id") or "").upper()
        if not TENANT_RE.fullmatch(tenant):
            return JSONResponse(status_code=400, content={"detail": "Missing / invalid X-Tenant-Id"})

        # 2) tomar el pool desde app.state y setear la GUC de manera segura
        pool: AsyncConnectionPool = request.app.state.pool  # lo ponemos en main.py
        async with pool.connection() as conn:
            await conn.execute("SELECT set_config(%s, %s, false)", (GUC_NAME, tenant))
            request.state.db = conn  # opcional: la conexión queda disponible para handlers

            # 3) seguir la cadena
            return await call_next(request)
