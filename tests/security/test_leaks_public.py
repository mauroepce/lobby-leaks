# tests/security/test_leaks_public.py
import os
import pytest
from dotenv import load_dotenv
import psycopg

pytestmark = pytest.mark.rls  # marca todo el módulo como RLS

# Carga .env solo en local; en CI ya viene por env del workflow
load_dotenv()

DSN = os.environ.get("DATABASE_URL")
if not DSN:
    raise RuntimeError("DATABASE_URL must be set (usa .env local o variables del CI)")

def _fetch_for(tenant_code: str):
    with psycopg.connect(DSN) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            # fija el tenant actual para RLS
            cur.execute("SELECT set_config('app.current_tenant', %s, false)", (tenant_code,))
            try:
                cur.execute("SET ROLE anonymous")
                cur.execute('SELECT id, status, "tenantCode" FROM "Leak" ORDER BY id')
                return cur.fetchall()
            finally:
                cur.execute("RESET ROLE")

@pytest.mark.parametrize("tenant", ["CL", "UY"])
def test_leaks_public_policy(tenant):
    rows = _fetch_for(tenant)
    assert len(rows) >= 1, f"Seed debe tener al menos 1 leak público para {tenant}"
    for _, status, tcode in rows:
        assert status == "public"
        assert tcode == tenant
