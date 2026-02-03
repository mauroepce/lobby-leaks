-- ============================================================================
-- Migration: Event table schema fix
-- Purpose: Align Event table with donation_persistence.py expectations
-- Changes:
--   - Rename "fecha" → "date"
--   - Drop "descripcion" column
--   - Add "metadata" JSONB column
--   - Update index from fecha to date
-- ============================================================================

-- Drop the old index that references "fecha"
DROP INDEX IF EXISTS "Event_fecha_idx";

-- Rename "fecha" column to "date"
ALTER TABLE "Event" RENAME COLUMN "fecha" TO "date";

-- Drop "descripcion" column (not used by donation pipeline)
ALTER TABLE "Event" DROP COLUMN IF EXISTS "descripcion";

-- Add "metadata" JSONB column for structured event data
ALTER TABLE "Event" ADD COLUMN "metadata" JSONB;

-- Create new index on "date" column (descending for time-series queries)
CREATE INDEX "Event_date_idx" ON "Event"("date" DESC);
