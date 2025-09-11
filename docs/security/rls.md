# Row Level Security (RLS) Documentation

## Overview

This document describes the Row Level Security policies implemented in the LobbyLeaks database to ensure proper data access control.

## Security Model

The LobbyLeaks security model follows the **principle of least privilege**:

- **Protected tables** have RLS enabled and forced
- **Anonymous role** has NO direct table access (raises `InsufficientPrivilege`)
- **Public access** is provided through controlled views with security barriers
- **Tenant isolation** is enforced at the database level

## RLS Status by Table

| Table | RLS Enabled | RLS Forced | Access Model |
|-------|-------------|------------|--------------|
| `Tenant` | ✅ | ✅ | No anonymous access |
| `User` | ✅ | ✅ | No anonymous access |
| `Document` | ✅ | ✅ | No anonymous access |
| `FundingRecord` | ✅ | ✅ | No anonymous access |
| `Leak` | ✅ | ✅ | Via `leaks_public_v` view only |

## Access Control Policies

### Protected Tables (Tenant, User, Document, FundingRecord)

**Security approach**: Permission revocation
- Anonymous role has **NO SELECT permissions**
- Direct access raises `InsufficientPrivilege` error
- No policies needed (access denied at permission level)

### Leak Table

**Security approach**: Controlled view access
- Anonymous role has **NO direct table access**
- Public access via `leaks_public_v` view with security barrier
- View filters: `status = 'public'` AND `tenantCode = current_setting('app.current_tenant')`

## Anonymous Role Permissions

The `anonymous` role has the following permissions:

```sql
-- Schema access
GRANT USAGE ON SCHEMA public TO anonymous;
REVOKE CREATE ON SCHEMA public FROM anonymous;

-- Table permissions (NONE for protected tables)
-- No SELECT grants on: Tenant, User, Document, FundingRecord, Leak

-- View permissions  
GRANT SELECT ON leaks_public_v TO anonymous;
```

## Tenant Context

All operations use tenant context via PostgreSQL settings:

```sql
SELECT set_config('app.current_tenant', 'CL', false);
```

Supported tenants: `CL`, `UY`

## Migration History

### Migrations Hash

| Migration | Date | Hash | Description |
|-----------|------|------|-------------|
| `20250728200458_init_schema` | 2025-07-28 | `dfc4c02` | Initial RLS setup |
| `20250819231939_leaks_public` | 2025-08-19 | `3c6b94d` | Leak table and public access |
| `20250901232731_rls_anonymous_deny_all` | 2025-09-01 | `3c6b94d` | Anonymous role setup |
| `20250901233943_rls_anonymous_schema_search_path` | 2025-09-01 | `3c6b94d` | Schema permissions |
| `20250903003316_leaks_public_view` | 2025-09-03 | `3c6b94d` | Public view with security barrier |
| `20250904024645_rls_anonymous_schema_usage` | 2025-09-04 | `3c6b94d` | Schema usage permissions |
| `20250909224227_fix_anonymous_rls_permissions` | 2025-09-09 | `465750d` | **Final security fix** |

### Last Review

- **Date**: 2025-09-10
- **Reviewer**: Claude Code
- **Status**: ✅ Security policies verified
- **Test Coverage**: RLS regression tests in `tests/security/test_rls_regression.py`

## Verification

To verify RLS implementation:

```bash
# Run RLS regression tests
make test-rls

# Manual verification
psql $DATABASE_URL -c "
SELECT relname, relrowsecurity, relforcerowsecurity 
FROM pg_class c 
JOIN pg_namespace n ON n.oid = c.relnamespace 
WHERE c.relkind='r' AND n.nspname='public' 
  AND c.relname IN ('Tenant', 'User', 'Document', 'FundingRecord', 'Leak');
"
```

Expected results:
- All tables: `relrowsecurity = true, relforcerowsecurity = true`
- Anonymous access to protected tables: `InsufficientPrivilege` error
- Anonymous access to public view: Success with filtered results

## Security Principles

1. **Defense in Depth**: Multiple layers (permissions + RLS + views)
2. **Fail Secure**: Deny by default, explicit grants only
3. **Tenant Isolation**: Strict separation by tenant code
4. **Audit Trail**: All changes tracked in migrations
5. **Regression Testing**: Automated security tests in CI/CD

---

> ⚠️ **Security Notice**: Any changes to these policies must be reviewed and tested thoroughly. Update this document when policies change.