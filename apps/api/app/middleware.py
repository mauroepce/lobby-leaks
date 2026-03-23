from __future__ import annotations

import re

from fastapi import HTTPException, Query, Request

TENANT_RE = re.compile(r"^[A-Z]{2}$")


async def resolve_tenant(
    request: Request,
    tenant: str | None = Query(None, description="ISO 3166-1 alpha-2 tenant code"),
) -> str:
    """Resolve tenant from query param or X-Tenant-Id header.

    Priority: query param > header. If both present and differ, return 400.
    """
    header_raw = request.headers.get("X-Tenant-Id") or ""
    header_val = header_raw.strip().upper() or None
    param_val = tenant.strip().upper() if tenant else None

    if param_val and header_val and param_val != header_val:
        raise HTTPException(
            status_code=400,
            detail="Conflicting tenant: query param and X-Tenant-Id header differ",
        )

    resolved = param_val or header_val
    if not resolved or not TENANT_RE.fullmatch(resolved):
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid tenant (provide ?tenant=XX or X-Tenant-Id header)",
        )

    return resolved
