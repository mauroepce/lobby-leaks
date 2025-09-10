-- Secure 'anonymous' role for testing/public reading
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anonymous') THEN
    CREATE ROLE anonymous NOLOGIN;
  END IF;
END $$;

-- Allows the DB owner (e.g. user 'lobbyleaks') to SET ROLE anonymous
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lobbyleaks') THEN
    GRANT anonymous TO lobbyleaks;
  END IF;
END $$;

-- Protected tables: User, Document, FundingRecord
-- 1) Grant SELECT (required for the query to reach RLS)
GRANT SELECT ON TABLE "User", "Document", "FundingRecord" TO anonymous;

-- 2) Ensure RLS enabled + forced (idempotent)
ALTER TABLE "User"          ENABLE ROW LEVEL SECURITY; ALTER TABLE "User"          FORCE ROW LEVEL SECURITY;
ALTER TABLE "Document"      ENABLE ROW LEVEL SECURITY; ALTER TABLE "Document"      FORCE ROW LEVEL SECURITY;
ALTER TABLE "FundingRecord" ENABLE ROW LEVEL SECURITY; ALTER TABLE "FundingRecord" FORCE ROW LEVEL SECURITY;

-- 3) (Re)create "deny-all" policies for anonymous => SELECT returns 0 rows
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='User' AND policyname='user_anonymous_deny_all') THEN
    DROP POLICY "user_anonymous_deny_all" ON "User";
  END IF;
  CREATE POLICY "user_anonymous_deny_all"
    ON "User"
    FOR SELECT
    TO anonymous
    USING (false);

  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='Document' AND policyname='document_anonymous_deny_all') THEN
    DROP POLICY "document_anonymous_deny_all" ON "Document";
  END IF;
  CREATE POLICY "document_anonymous_deny_all"
    ON "Document"
    FOR SELECT
    TO anonymous
    USING (false);

  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='FundingRecord' AND policyname='funding_anonymous_deny_all') THEN
    DROP POLICY "funding_anonymous_deny_all" ON "FundingRecord";
  END IF;
  CREATE POLICY "funding_anonymous_deny_all"
    ON "FundingRecord"
    FOR SELECT
    TO anonymous
    USING (false);
END $$;
