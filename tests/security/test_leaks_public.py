# tests/security/test_leaks_public.py
import os
import pytest
from dotenv import load_dotenv
import psycopg

# Load .env only locally; in CI it comes via workflow env
load_dotenv()

DSN = os.environ.get("DATABASE_URL")

# Use skipif at module scope so the file can be COLLECTED even when no DB is
# available (the `test` job in CI runs with no DB and excludes rls-marked
# tests via `-m "not rls"` — that filter only kicks in after collection, so
# the previous `raise RuntimeError(...)` at import time broke collection).
pytestmark = [
    pytest.mark.rls,
    pytest.mark.skipif(not DSN, reason="DATABASE_URL must be set in env to run RLS tests"),
]

def _fetch_from_view(tenant: str):
    with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant', %s, false)", (tenant,))
        cur.execute("SET ROLE anonymous")
        try:
            cur.execute('SELECT id, status, "tenantCode" FROM public.leaks_public_v ORDER BY id')
            return cur.fetchall()
        finally:
            cur.execute("RESET ROLE")

@pytest.mark.parametrize("tenant", ["CL", "UY"])
def test_view_returns_only_public_for_tenant(tenant):
    rows = _fetch_from_view(tenant)
    assert len(rows) >= 1
    for _, status, tcode in rows:
        assert status == "public"
        assert tcode == tenant

def test_anonymous_cannot_read_base_table():
    with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SET ROLE anonymous")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute('SELECT count(*) FROM "public"."Leak"')