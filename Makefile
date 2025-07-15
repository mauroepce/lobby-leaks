install:
	pnpm install

lint:
	pnpm run lint

test:
	pnpm test

mcp-install:
	python3 -m pip install --upgrade pip setuptools
	python3 -m pip install -r services/mcp-hub/requirements.txt

mcp-test:
	uvicorn app.main:app --app-dir services/mcp-hub --host 0.0.0.0 --port 8000 & \
	SERVER_PID=$$!; \
	sleep 2; \
	pytest -q services/mcp-hub/tests; \
	kill $$SERVER_PID


