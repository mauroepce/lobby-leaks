# Contributing to LobbyLeaks

## Branch workflow  
1. **Feature branch** – start from `main` with a prefix such as  
   `feat/`, `fix/`, `chore/`, etc.  
2. **Pull Request** – open a PR to `main` and link the issue  
   (e.g. `Fixes #42`).  
3. **Status checks** – PRs **must** be green on *lint* + *tests* + *RLS* before merge.  
4. **Self-review** – while we have few maintainers, use the PR checklist yourself.  
5. **Merge** – “Squash & merge” keeps history tidy.

---

## Local checklist 🛠️

Run **all** of the following before opening a PR – they mirror the CI matrix:

```bash
# 0) (optional) create an isolated Python env
python -m venv .venv && source .venv/bin/activate

# 1) install every dependency (Node + Python)
make install

# 2) run unit + integration tests (RLS suite excluded)
make test

# 3) run Row-Level-Security (RLS) tests
RUN_RLS=1 make test-rls      # spins up Postgres, resets schema, executes checks

# 4) lint JavaScript/TypeScript sources
make lint
```
> *Why the extra flag?* The RLS suite manipulates Postgres users and takes a few extra seconds, so we gate it behind the `RUN_RLS` environment variable (a common pattern for optional security tests).