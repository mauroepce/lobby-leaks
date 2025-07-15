# services/mcp-hub/app/main.py
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(
    title="LobbyLeaks MCP Stub",
    version="0.1.0",
    docs_url="/docs", redoc_url=None
)

@app.post("/rpc2")
async def rpc2(req: Request):
    """
    Very basic JSON-RPC stub: read the 'method' field and
    respond 501 for our four tool names, 400 otherwise.
    """
    payload = await req.json()
    method = payload.get("method", "")
    if method in ("fetch_pdf", "ocr_pdf", "summarise_doc", "entity_link"):
        # JSON-RPC errors normally go in {"error":…} envelope, but
        # our Acceptance Criteria only says “return 501”, so:
        raise HTTPException(status_code=501, detail=f"{method} not implemented yet")
    raise HTTPException(status_code=400, detail="Unknown method")

# (No other endpoints needed)
