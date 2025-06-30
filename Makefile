install:
	pnpm install && pip install -r requirements.txt

test:
	pnpm test && pytest -q

lint:
	pnpm run lint
