# services/mcp-hub/tests/test_stub.py
import httpx

BASE = "http://localhost:8000"
PAYLOAD = {"jsonrpc": "2.0", "id": 1, "method": None, "params": {}}
HEADERS = {"X-Tenant-Id": "CL"}

def call(method: str) -> httpx.Response:
    with httpx.Client(base_url=BASE, timeout=3.0) as c:
        return c.post("/rpc2", json={**PAYLOAD, "method": method}, headers=HEADERS)

def test_all_stubs():
    for m in ("fetch_pdf", "ocr_pdf", "summarise_doc", "entity_link"):
        r = call(m)
        assert r.status_code == 501
