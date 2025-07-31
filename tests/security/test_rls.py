import os, pytest, psycopg
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())             # always search upward for .env
DSN = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")

# Skip unless the dedicated pipeline sets RUN_RLS=1
pytestmark = pytest.mark.rls
if os.getenv("RUN_RLS") != "1" or not DSN:
    pytest.skip("RLS tests run only in the rls-tests workflow",
                allow_module_level=True)

@pytest.fixture(scope="module")
def conn():
    conn = psycopg.connect(DSN)
    conn.execute("SET ROLE lobbyleaks;")
    yield conn
    conn.close()

@pytest.mark.parametrize("table", ["Tenant","User","Document","FundingRecord"])
def test_rls_default_deny(conn, table):
    with conn.cursor() as cur:
        cur.execute(f'SELECT count(*) FROM "{table}";')
        assert cur.fetchone()[0] == 0
