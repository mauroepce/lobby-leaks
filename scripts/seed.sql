-- Tenants (configurable)
WITH tenants(code, name) AS (
  SELECT *
  FROM unnest(
    ARRAY['CL','UY']::text[], 
    ARRAY['Chile','Uruguay']::text[] 
  )
)
INSERT INTO "Tenant"("code","name")
SELECT code, name FROM tenants
ON CONFLICT ("code") DO NOTHING;

-- Leaks (1 public + 1 draft per tenant)
WITH tenants(code) AS (
  SELECT * FROM unnest(ARRAY['CL','UY']::text[])
)
INSERT INTO "Leak"("id","title","status","tenantCode")
SELECT lower(code)||'_pub_1',  code||' pública 1',  'public', code FROM tenants
UNION ALL
SELECT lower(code)||'_draft_1',code||' borrador 1','draft',  code FROM tenants
ON CONFLICT ("id") DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- Users (protected by RLS; the 'anonymous' role should NOT be able to view them)
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO "User"("id","email","role","tenantCode") VALUES
  ('user_cl_1','alice.cl@example.org','admin','CL'),
  ('user_cl_2','bob.cl@example.org','viewer','CL'),
  ('user_uy_1','ana.uy@example.org','admin','UY'),
  ('user_uy_2','beto.uy@example.org','viewer','UY')
ON CONFLICT ("id") DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- Documents (protected by RLS; refer to existing uploader)
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO "Document"("id","url","tenantCode","uploaderId") VALUES
  ('doc_cl_1','https://example.org/cl/doc1.pdf','CL','user_cl_1'),
  ('doc_cl_2','https://example.org/cl/doc2.pdf','CL','user_cl_2'),
  ('doc_uy_1','https://example.org/uy/doc1.pdf','UY','user_uy_1'),
  ('doc_uy_2','https://example.org/uy/doc2.pdf','UY','user_uy_2')
ON CONFLICT ("id") DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- FundingRecord (protected by RLS)
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO "FundingRecord"("id","politician","amount","source","tenantCode") VALUES
  ('fund_cl_1','Diputada X',  '100000.00','donante_a','CL'),
  ('fund_cl_2','Senador Y',   '250000.00','donante_b','CL'),
  ('fund_uy_1','Diputada U',  '150000.00','donante_c','UY'),
  ('fund_uy_2','Senador V',   '300000.00','donante_d','UY')
ON CONFLICT ("id") DO NOTHING;

-- Note: We don't modify roles or GRANTs here; that's handled in the RLS migration scripts.
-- This seed script only ensures that there is "real" data that RLS should hide from the anonymous role.

