import os
import pytest
from dotenv import load_dotenv
import psycopg
from psycopg.errors import InsufficientPrivilege

pytestmark = pytest.mark.rls

load_dotenv()
DSN = os.environ.get("DATABASE_URL")
if not DSN:
    raise RuntimeError("DATABASE_URL must be set in env to run tests")

# Tables where the anonymous role should NOT see anything (zero rows or no permission)
PROTECTED_TABLES = ["Tenant", "User", "Document", "FundingRecord"]

# Tables where RLS should be enabled/forced
CHECK_RLS_TABLES = ["Tenant", "User", "Document", "FundingRecord", "Leak"]

def _conn():
    return psycopg.connect(DSN, autocommit=True)

def test_rls_is_enabled_and_forced():
    q = """
    SELECT c.relname,
           c.relrowsecurity,      -- ENABLE RLS
           c.relforcerowsecurity  -- FORCE RLS
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind='r' AND n.nspname='public' AND c.relname = ANY(%s)
    ORDER BY c.relname;
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(q, (CHECK_RLS_TABLES,))
        rows = cur.fetchall()
    found = {name: (en, fo) for (name, en, fo) in rows}
    for t in CHECK_RLS_TABLES:
        assert t in found, f"Tabla {t} don't exist"
        en, fo = found[t]
        assert en is True, f"RLS not enable in {t}"
        assert fo is True, f"RLS not forced into {t}"

@pytest.mark.parametrize("tenant", ["CL", "UY"])
def test_anonymous_cannot_read_protected_tables(tenant):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant', %s, false)", (tenant,))
        cur.execute("SET ROLE anonymous")
        try:
            for t in PROTECTED_TABLES:
                # 👇 fully-qualified para evitar líos con search_path
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(f'SELECT count(*) FROM "public"."{t}"')
        finally:
            cur.execute("RESET ROLE")
