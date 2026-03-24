from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..db import search_entities
from ..middleware import resolve_tenant
from ..schemas import SearchResponse

router = APIRouter(prefix="/api/v1")

MAX_LIMIT = 100


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Search term"),
    tenant: str = Depends(resolve_tenant),
    limit: int = Query(20, ge=1, le=MAX_LIMIT, description="Max results"),
) -> SearchResponse:
    """Search persons and organisations by name or RUT."""
    pool = request.app.state.pool
    results, total = await search_entities(pool, tenant, q, limit)
    return SearchResponse(results=results, total=total)
