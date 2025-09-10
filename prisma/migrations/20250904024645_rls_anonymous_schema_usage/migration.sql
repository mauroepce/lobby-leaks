-- Asegura que el rol exista
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anonymous') THEN
    CREATE ROLE anonymous NOLOGIN;
  END IF;
END $$;

-- El rol anonymous necesita USAGE en el schema para poder consultar vistas allí
GRANT USAGE ON SCHEMA public TO anonymous;

-- Nos aseguramos de no dar capacidades de creación en el schema
REVOKE CREATE ON SCHEMA public FROM anonymous;
