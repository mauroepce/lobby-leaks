from __future__ import annotations

from pydantic import BaseModel


class EntityResult(BaseModel):
    id: str
    type: str  # "person" | "organisation"
    label: str
    rut: str | None


class SearchResponse(BaseModel):
    results: list[EntityResult]
    total: int
