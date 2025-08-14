# services/mcp-hub/tests/test_tenant_header.py
import httpx

BASE = "http://localhost:8000"
PAYLOAD = {"jsonrpc": "2.0", "id": 1, "method": "fetch_pdf", "params": {}}

def test_missing_header_is_400():
    with httpx.Client(base_url=BASE, timeout=3.0) as c:
        r = c.post("/rpc2", json=PAYLOAD)
    assert r.status_code == 400

def test_valid_header_is_501():
    with httpx.Client(base_url=BASE, timeout=3.0) as c:
        r = c.post("/rpc2", json=PAYLOAD, headers={"X-Tenant-Id": "CL"})
    assert r.status_code == 501

