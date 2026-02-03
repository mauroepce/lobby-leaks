-- ============================================================================
-- Migration: Graph Analysis Views
-- Purpose: Create analysis views for donation insights
-- Views:
--   - v_donations_graph: Flattened donation view with donor/candidate info
--   - v_top_donors_by_candidate: Aggregation of donations by candidate
-- ============================================================================

-- ============================================================================
-- View: v_donations_graph
-- Flattened view of donation events with donor and candidate information.
-- Extracts structured data from Event.metadata JSONB.
-- ============================================================================

CREATE VIEW v_donations_graph AS
SELECT
    e.id AS event_id,
    e."tenantCode" AS tenant_code,
    e."externalId" AS external_id,
    e.date AS donation_date,

    -- Extract amount from metadata (stored as integer CLP)
    NULLIF(e.metadata->>'amount', '')::bigint AS amount,

    -- Extract campaign year from metadata
    NULLIF(e.metadata->>'campaign_year', '')::int AS campaign_year,

    -- Donor information
    e.metadata->>'donor_name' AS donor_name,
    COALESCE(donor_edge."toPersonId", donor_edge."toOrgId") AS donor_id,
    CASE
        WHEN donor_edge."toPersonId" IS NOT NULL THEN 'person'
        WHEN donor_edge."toOrgId" IS NOT NULL THEN 'organisation'
        ELSE NULL
    END AS donor_type,
    e.metadata->>'donor_matched_by' AS donor_matched_by,

    -- Candidate information
    e.metadata->>'candidate_name' AS candidate_name,
    candidate_edge."toPersonId" AS candidate_id,
    e.metadata->>'candidate_matched_by' AS candidate_matched_by,

    -- Additional metadata
    e.metadata->>'election_type' AS election_type,
    e.metadata->>'candidate_party' AS candidate_party,

    e."createdAt" AS created_at

FROM "Event" e
LEFT JOIN "Edge" donor_edge
    ON donor_edge."eventId" = e.id
    AND donor_edge.label = 'DONANTE'
LEFT JOIN "Edge" candidate_edge
    ON candidate_edge."eventId" = e.id
    AND candidate_edge.label = 'DONATARIO'
WHERE e.kind = 'donation';

-- ============================================================================
-- View: v_top_donors_by_candidate
-- Aggregates donations by candidate and donor.
-- Shows total amount and donation count per donor-candidate pair.
-- ============================================================================

CREATE VIEW v_top_donors_by_candidate AS
SELECT
    vdg.tenant_code,
    vdg.candidate_id,
    vdg.candidate_name,
    vdg.donor_id,
    vdg.donor_name,
    vdg.donor_type,
    SUM(vdg.amount) AS total_amount,
    COUNT(*) AS donation_count
FROM v_donations_graph vdg
WHERE vdg.candidate_id IS NOT NULL
  AND vdg.donor_id IS NOT NULL
  AND vdg.amount IS NOT NULL
GROUP BY
    vdg.tenant_code,
    vdg.candidate_id,
    vdg.candidate_name,
    vdg.donor_id,
    vdg.donor_name,
    vdg.donor_type
ORDER BY total_amount DESC;
