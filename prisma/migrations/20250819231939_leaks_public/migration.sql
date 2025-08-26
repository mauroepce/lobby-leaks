-- CreateTable
CREATE TABLE "Leak" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,

    CONSTRAINT "Leak_pkey" PRIMARY KEY ("id")
);

-- (Opcional) Restringe status a 'public'|'draft'
ALTER TABLE "Leak"
  ADD CONSTRAINT "leak_status_chk"
  CHECK ("status" IN ('public','draft'));

-- Índice por tenant
CREATE INDEX "Leak_tenantCode_idx" ON "Leak"("tenantCode");

-- FK a Tenant
ALTER TABLE "Leak"
  ADD CONSTRAINT "Leak_tenantCode_fkey"
  FOREIGN KEY ("tenantCode") REFERENCES "Tenant"("code")
  ON DELETE RESTRICT ON UPDATE CASCADE;

-- Asegura rol 'anonymous' (para pruebas/lectura pública)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anonymous') THEN
    CREATE ROLE anonymous NOLOGIN;
  END IF;
END $$;

-- Permite que el usuario de la app pueda SET ROLE anonymous (tests/CI)
GRANT anonymous TO lobbyleaks;

-- RLS en la tabla
ALTER TABLE "Leak" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Leak" FORCE  ROW LEVEL SECURITY;

-- Permiso base de lectura (RLS seguirá filtrando filas)
GRANT SELECT ON TABLE "Leak" TO anonymous;

-- (Re)crea la policy: SOLO filas públicas DEL tenant activo
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'Leak'
      AND policyname = 'leaks_public'
  ) THEN
    DROP POLICY "leaks_public" ON "Leak";
  END IF;

  CREATE POLICY "leaks_public"
    ON "Leak"
    FOR SELECT
    TO anonymous
    USING (
      "status" = 'public'
      AND "tenantCode" = current_setting('app.current_tenant', true)
    );
END $$;
