-- CreateTable
CREATE TABLE "LobbyEventRaw" (
    "id" TEXT NOT NULL,
    "externalId" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "rawData" JSONB NOT NULL,
    "fecha" TIMESTAMP(3),
    "monto" DECIMAL(65,30),
    "institucion" TEXT,
    "destino" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "LobbyEventRaw_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "LobbyEventRaw_externalId_key" ON "LobbyEventRaw"("externalId");

-- CreateIndex
CREATE INDEX "LobbyEventRaw_tenantCode_idx" ON "LobbyEventRaw"("tenantCode");

-- CreateIndex
CREATE INDEX "LobbyEventRaw_externalId_idx" ON "LobbyEventRaw"("externalId");

-- CreateIndex
CREATE INDEX "LobbyEventRaw_kind_fecha_idx" ON "LobbyEventRaw"("kind", "fecha" DESC);

-- Enable & force RLS (consistent with existing tables)
ALTER TABLE "LobbyEventRaw" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "LobbyEventRaw" FORCE  ROW LEVEL SECURITY;
