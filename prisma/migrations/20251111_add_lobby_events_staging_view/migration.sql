-- CreateView: lobby_events_staging
-- Normalized/derived fields from LobbyEventRaw for efficient querying

CREATE OR REPLACE VIEW lobby_events_staging AS
SELECT
  -- Core identifiers
  id,
  "externalId",
  "tenantCode",
  kind,

  -- Normalized person fields (common to all kinds)
  -- Note: rawData is stored as JSONB, so we can use ->> operator directly
  ("rawData"::jsonb)->>'nombres' as nombres,
  ("rawData"::jsonb)->>'apellidos' as apellidos,
  CONCAT_WS(' ', ("rawData"::jsonb)->>'nombres', ("rawData"::jsonb)->>'apellidos') as "nombresCompletos",
  ("rawData"::jsonb)->>'cargo' as cargo,

  -- Temporal fields
  fecha,
  EXTRACT(YEAR FROM fecha)::int as year,
  EXTRACT(MONTH FROM fecha)::int as month,

  -- Kind-specific: institucion
  -- Extract institution name based on event kind
  CASE
    WHEN kind = 'audiencia' THEN COALESCE(
      ("rawData"::jsonb)->>'sujeto_pasivo',
      ("rawData"::jsonb)->>'nombre_institucion',
      ("rawData"::jsonb)->>'institucion'
    )
    WHEN kind = 'viaje' THEN COALESCE(
      ("rawData"::jsonb)->'institucion'->>'nombre',
      ("rawData"::jsonb)->>'institucion_destino',
      ("rawData"::jsonb)->>'organizador'
    )
    WHEN kind = 'donativo' THEN COALESCE(
      ("rawData"::jsonb)->>'institucion_donante',
      ("rawData"::jsonb)->>'donante',
      ("rawData"::jsonb)->>'institucion'
    )
    ELSE NULL
  END as institucion,

  -- Kind-specific: destino (mainly for viajes)
  CASE
    WHEN kind = 'viaje' THEN COALESCE(
      ("rawData"::jsonb)->>'destino',
      CONCAT_WS(', ', ("rawData"::jsonb)->>'ciudad_destino', ("rawData"::jsonb)->>'pais_destino')
    )
    ELSE NULL
  END as destino,

  -- Kind-specific: monto (mainly for donativos, may exist in viajes)
  CASE
    WHEN kind = 'donativo' THEN
      CASE
        WHEN ("rawData"::jsonb)->>'monto' ~ '^[0-9]+\.?[0-9]*$'
          THEN (("rawData"::jsonb)->>'monto')::decimal
        ELSE NULL
      END
    WHEN kind = 'viaje' THEN
      CASE
        WHEN ("rawData"::jsonb)->>'costo_total' ~ '^[0-9]+\.?[0-9]*$'
          THEN (("rawData"::jsonb)->>'costo_total')::decimal
        ELSE NULL
      END
    ELSE NULL
  END as monto,

  -- Metadata: SHA256 hash of rawData for change detection
  ENCODE(SHA256(("rawData"::jsonb)::text::bytea), 'hex') as "rawDataHash",

  -- Metadata: Size of rawData for debugging/monitoring
  LENGTH(("rawData"::jsonb)::text) as "rawDataSize",

  -- Timestamps
  "createdAt",
  "updatedAt"

FROM "LobbyEventRaw";

-- Create indexes on the view (PostgreSQL 11+)
-- Note: Indexes on views require the view to be materialized OR base table indexes
-- Since we're using a simple VIEW (not MATERIALIZED), queries will use indexes on LobbyEventRaw

-- Add comment for documentation
COMMENT ON VIEW lobby_events_staging IS 'Staging layer with normalized/derived fields from LobbyEventRaw. Provides kind-specific field extraction and temporal aggregations.';
