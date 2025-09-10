# tests/security/test_leaks_public.py
import os
import pytest
from dotenv import load_dotenv
import psycopg

pytestmark = pytest.mark.rls  # mark the entire module as RLS

# Load .env only locally; in CI it comes via workflow env
load_dotenv()

DSN = os.environ.get("DATABASE_URL")
if not DSN:
    raise RuntimeError("DATABASE_URL must be set in env to run tests")

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