from __future__ import annotations

from psycopg_pool import AsyncConnectionPool

from .schemas import EntityResult

SEARCH_SQL = """
SELECT id, 'person' AS type, "normalizedName" AS label, rut
FROM "Person"
WHERE "tenantCode" = %(tenant)s
  AND ("normalizedName" ILIKE %(pattern)s OR "rut" ILIKE %(pattern)s)

UNION ALL

SELECT id, 'organisation' AS type, "normalizedName" AS label, rut
FROM "Organisation"
WHERE "tenantCode" = %(tenant)s
  AND ("normalizedName" ILIKE %(pattern)s OR "rut" ILIKE %(pattern)s)

ORDER BY label
LIMIT %(limit)s
"""

COUNT_SQL = """
SELECT
  (SELECT count(*) FROM "Person"
   WHERE "tenantCode" = %(tenant)s
     AND ("normalizedName" ILIKE %(pattern)s OR "rut" ILIKE %(pattern)s))
  +
  (SELECT count(*) FROM "Organisation"
   WHERE "tenantCode" = %(tenant)s
     AND ("normalizedName" ILIKE %(pattern)s OR "rut" ILIKE %(pattern)s))
AS total
"""


async def search_entities(
    pool: AsyncConnectionPool,
    tenant: str,
    query: str,
    limit: int = 20,
) -> tuple[list[EntityResult], int]:
    """Search Person and Organisation tables by normalizedName or rut."""
    pattern = f"%{query}%"
    params = {"tenant": tenant, "pattern": pattern, "limit": limit}

    async with pool.connection() as conn:
        # Fetch matching rows
        cursor = await conn.execute(SEARCH_SQL, params)
        rows = await cursor.fetchall()
        results = [
            EntityResult(id=r[0], type=r[1], label=r[2], rut=r[3])
            for r in rows
        ]

        # Fetch total count
        cursor = await conn.execute(COUNT_SQL, params)
        row = await cursor.fetchone()
        total = row[0] if row else 0

    return results, total
