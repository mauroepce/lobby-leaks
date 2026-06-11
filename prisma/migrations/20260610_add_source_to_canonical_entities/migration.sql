-- Add provenance column to canonical entities.
--
-- services/info_lobby_sync/persistence.py writes the ingestion source
-- ("infolobby_sparql") on every UPSERT to Person and Organisation, but the
-- column was never created. Inserts failed with
--   ERROR 42703: column "source" of relation "Person" does not exist
-- and aborted the surrounding transaction.
--
-- Nullable so existing rows backfill to NULL without a default rewrite.

ALTER TABLE "Person"
  ADD COLUMN IF NOT EXISTS "source" TEXT;

ALTER TABLE "Organisation"
  ADD COLUMN IF NOT EXISTS "source" TEXT;
