import httpx, asyncio

async def call(method):
    async with httpx.AsyncClient(base_url="http://localhost:8000") as c:
        r = await c.post("/rpc2", json={"jsonrpc":"2.0","id":1,"method":method,"params":{}})
    assert r.status_code == 501

def test_all_stubs():
    for m in ("fetch_pdf","ocr_pdf","summarise_doc","entity_link"):
        asyncio.run(call(m))
