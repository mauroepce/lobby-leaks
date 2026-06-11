-- Make the Edge logical-uniqueness constraint NULL-safe.
--
-- The original UNIQUE constraint on
--   ("eventId", "fromPersonId", "fromOrgId", "toPersonId", "toOrgId", label)
-- followed Postgres' default treatment of NULLs as distinct. For
-- participations the from* columns are ALWAYS NULL, so two semantically-
-- identical edges never conflicted and re-runs of the ingest silently
-- duplicated every edge. Idempotency was therefore broken before today.
--
-- Postgres 15+ added `NULLS NOT DISTINCT` for exactly this case. Supabase
-- runs Postgres 17, so we can use it.

-- Step 1 — purge existing duplicate groups (keep the earliest createdAt
-- per logical key). One-time cleanup; the new constraint prevents
-- recurrence from here on.
DELETE FROM "Edge"
WHERE id IN (
  SELECT id FROM (
    SELECT id,
           row_number() OVER (
             PARTITION BY "eventId", "fromPersonId", "fromOrgId",
                          "toPersonId", "toOrgId", "label"
             ORDER BY "createdAt" ASC, id ASC
           ) AS rn
    FROM "Edge"
  ) t
  WHERE t.rn > 1
);

-- Step 2 — drop the buggy constraint + its underlying index.
-- DROP CONSTRAINT + CASCADE handles cases where the index was created
-- separately and only later attached as the constraint backing.
ALTER TABLE "Edge"
  DROP CONSTRAINT IF EXISTS
  "Edge_eventId_fromPersonId_fromOrgId_toPersonId_toOrgId_label_ke"
  CASCADE;

-- Belt + suspenders: drop the index by name in case it survived the
-- constraint drop (e.g. it was added independently).
DROP INDEX IF EXISTS
  "Edge_eventId_fromPersonId_fromOrgId_toPersonId_toOrgId_label_ke";

-- Step 3 — recreate with NULLS NOT DISTINCT. Distinct constraint name
-- (`_nnd_uniq` suffix) so a future Prisma-managed introspection / push
-- doesn't try to "fix" us back to the old behavior.
ALTER TABLE "Edge"
  ADD CONSTRAINT "Edge_logical_nnd_uniq"
  UNIQUE NULLS NOT DISTINCT (
    "eventId", "fromPersonId", "fromOrgId",
    "toPersonId", "toOrgId", "label"
  );
