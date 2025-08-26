-- Tenants
INSERT INTO "Tenant"("code","name") VALUES
  ('CL','Chile'),
  ('UY','Uruguay')
ON CONFLICT ("code") DO NOTHING;

-- Leaks de ejemplo
INSERT INTO "Leak"("id","title","status","tenantCode") VALUES
  ('cl_pub_1',  'CL pública 1',  'public', 'CL'),
  ('cl_draft_1','CL borrador 1','draft',  'CL'),
  ('uy_pub_1',  'UY pública 1',  'public', 'UY'),
  ('uy_draft_1','UY borrador 1','draft',  'UY')
ON CONFLICT ("id") DO NOTHING;
