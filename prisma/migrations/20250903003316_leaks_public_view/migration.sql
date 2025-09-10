DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='Leak' AND policyname='leaks_public'
  ) THEN
    DROP POLICY "leaks_public" ON "Leak";
  END IF;
END $$;

-- Isolate the base table: the 'anonymous' role should NOT read it directly
REVOKE ALL ON TABLE "Leak" FROM anonymous;

-- Read-only view for the 'anonymous' role, with security barrier
DROP VIEW IF EXISTS leaks_public_v;
CREATE VIEW leaks_public_v
WITH (security_barrier = true) AS
SELECT id, title, status, "tenantCode"
FROM "Leak"
WHERE status = 'public'
  AND "tenantCode" = current_setting('app.current_tenant', true);

GRANT SELECT ON leaks_public_v TO anonymous;
