# Contributing to LobbyLeaks

## Branch workflow

1. **Create a feature branch** off `main` with a clear prefix:  
   `feat/…`, `fix/…`, `chore/…`, `docs/…`, `refactor/…`.
2. **Open a Pull Request** to `main` and link the issue (e.g. `Fixes #42`).
3. **❗ Status checks must be green** (lint + tests + RLS + MCP e2e) before merge.
4. **Self-review** using the checklist below.
5. **Merge** with **Squash & merge** to keep history tidy.

> 💡 **Tip**: prefer Conventional Commit messages (e.g. `feat(chile): add tenant header middleware`).

---

## 📋 Requirements

- **Node** ≥ 20  
- **Python** ≥ 3.12  
- **Docker Desktop** (Postgres 16 runs in a container)

---

## 🚀 Local setup (one-time)

```bash
# optional but recommended
python -m venv .venv && source .venv/bin/activate  # Win: .venv\Scripts\activate

cp .env.example .env

make bootstrap    # installs repo deps + MCP hub deps
```

## ⚡ Day-to-day

```bash
make quick        # lint + unit tests + MCP e2e (Docker)
make test-all     # todos los tests (lint + unit + template + MCP e2e)
```

## ✅ Full pre-PR checklist

**❗ Run all before opening a PR — mirrors CI:**

```bash
# 1) Full pipeline: DB up, lint, unit, RLS, MCP e2e
make verify

# (optional) same as above but also tears down containers/volumes at the end
make verify-clean
```

### What `verify` covers

- **Lint** (ESLint)
- **Unit tests** (Jest + Pytest)
- **RLS tests** (`RUN_RLS=1 make test-rls`)
- **MCP e2e** (`make mcp-test-e2e`): builds the hub image, brings up Postgres, waits for `/rpc2`, runs hub tests, then stops only the hub container.

### Alternative: `make test-all`

Si solo necesitas verificar tests (sin RLS ni DB setup completo):

```bash
make test-all     # lint + unit + template (57 tests) + MCP e2e
```

**Need to poke the hub manually?** `make mcp-curl`
- **Expected**: 400 without header, 501 with `X-Tenant-Id: CL`.

---

## 🔍 PR self-review checklist

- [ ] **Branch name is descriptive** (e.g. `feat/chile-tenant-context`).
- [ ] **Added/updated tests** (unit and/or e2e) and they pass locally.
- [ ] **❗ `make verify` is green locally**; CI badge turns green on the PR.
- [ ] **No secrets committed** (`.env`, passwords, tokens).
- [ ] **Docs updated** when behavior or API changed (README/OpenAPI/notes).
- [ ] **Changes are minimal, focused, and readable**.