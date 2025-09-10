-- Fix RLS permissions for anonymous role to ensure consistent security behavior
-- All protected tables should deny access completely (throw InsufficientPrivilege)
-- instead of using policies that return 0 rows

-- Revoke SELECT permissions from anonymous role on protected tables
REVOKE SELECT ON TABLE "User" FROM anonymous;
REVOKE SELECT ON TABLE "Document" FROM anonymous;
REVOKE SELECT ON TABLE "FundingRecord" FROM anonymous;

-- Drop the existing deny-all policies since they're no longer needed
-- (the anonymous role won't have table access at all)
DROP POLICY IF EXISTS "user_anonymous_deny_all" ON "User";
DROP POLICY IF EXISTS "document_anonymous_deny_all" ON "Document";
DROP POLICY IF EXISTS "funding_anonymous_deny_all" ON "FundingRecord";