install:
	pnpm install && pip install -r requirements.txt

test:
	pnpm test && pytest -q

mcp-run:
	uvicorn services.mcp-hub.app.main:app --reload

lint:
	pnpm run lint
