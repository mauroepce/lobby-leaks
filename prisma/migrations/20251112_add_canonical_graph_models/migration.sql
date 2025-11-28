-- CreateTable
CREATE TABLE "Person" (
    "id" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,
    "rut" TEXT,
    "normalizedName" TEXT NOT NULL,
    "nombres" TEXT NOT NULL,
    "apellidos" TEXT NOT NULL,
    "nombresCompletos" TEXT NOT NULL,
    "cargo" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Person_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Organisation" (
    "id" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,
    "rut" TEXT,
    "normalizedName" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "tipo" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Organisation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Event" (
    "id" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,
    "externalId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "fecha" TIMESTAMP(3),
    "descripcion" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Event_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Edge" (
    "id" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,
    "fromPersonId" TEXT,
    "fromOrgId" TEXT,
    "toPersonId" TEXT,
    "toOrgId" TEXT,
    "label" TEXT NOT NULL,
    "eventId" TEXT NOT NULL,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Edge_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Person_tenantCode_idx" ON "Person"("tenantCode");

-- CreateIndex
CREATE INDEX "Person_rut_idx" ON "Person"("rut");

-- CreateIndex
CREATE INDEX "Person_normalizedName_idx" ON "Person"("normalizedName");

-- CreateIndex
CREATE UNIQUE INDEX "Person_tenantCode_rut_key" ON "Person"("tenantCode", "rut");

-- CreateIndex
CREATE UNIQUE INDEX "Person_tenantCode_normalizedName_key" ON "Person"("tenantCode", "normalizedName");

-- CreateIndex
CREATE INDEX "Organisation_tenantCode_idx" ON "Organisation"("tenantCode");

-- CreateIndex
CREATE INDEX "Organisation_rut_idx" ON "Organisation"("rut");

-- CreateIndex
CREATE INDEX "Organisation_normalizedName_idx" ON "Organisation"("normalizedName");

-- CreateIndex
CREATE INDEX "Organisation_tipo_idx" ON "Organisation"("tipo");

-- CreateIndex
CREATE UNIQUE INDEX "Organisation_tenantCode_rut_key" ON "Organisation"("tenantCode", "rut");

-- CreateIndex
CREATE UNIQUE INDEX "Organisation_tenantCode_normalizedName_key" ON "Organisation"("tenantCode", "normalizedName");

-- CreateIndex
CREATE INDEX "Event_tenantCode_idx" ON "Event"("tenantCode");

-- CreateIndex
CREATE INDEX "Event_kind_idx" ON "Event"("kind");

-- CreateIndex
CREATE INDEX "Event_fecha_idx" ON "Event"("fecha" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "Event_tenantCode_externalId_kind_key" ON "Event"("tenantCode", "externalId", "kind");

-- CreateIndex
CREATE INDEX "Edge_tenantCode_idx" ON "Edge"("tenantCode");

-- CreateIndex
CREATE INDEX "Edge_label_idx" ON "Edge"("label");

-- CreateIndex
CREATE INDEX "Edge_eventId_idx" ON "Edge"("eventId");

-- CreateIndex
CREATE INDEX "Edge_fromPersonId_idx" ON "Edge"("fromPersonId");

-- CreateIndex
CREATE INDEX "Edge_fromOrgId_idx" ON "Edge"("fromOrgId");

-- CreateIndex
CREATE INDEX "Edge_toPersonId_idx" ON "Edge"("toPersonId");

-- CreateIndex
CREATE INDEX "Edge_toOrgId_idx" ON "Edge"("toOrgId");

-- CreateIndex
CREATE UNIQUE INDEX "Edge_eventId_fromPersonId_fromOrgId_toPersonId_toOrgId_label_key" ON "Edge"("eventId", "fromPersonId", "fromOrgId", "toPersonId", "toOrgId", "label");

-- AddForeignKey
ALTER TABLE "Edge" ADD CONSTRAINT "Edge_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES "Event"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Edge" ADD CONSTRAINT "Edge_fromPersonId_fkey" FOREIGN KEY ("fromPersonId") REFERENCES "Person"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Edge" ADD CONSTRAINT "Edge_fromOrgId_fkey" FOREIGN KEY ("fromOrgId") REFERENCES "Organisation"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Edge" ADD CONSTRAINT "Edge_toPersonId_fkey" FOREIGN KEY ("toPersonId") REFERENCES "Person"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Edge" ADD CONSTRAINT "Edge_toOrgId_fkey" FOREIGN KEY ("toOrgId") REFERENCES "Organisation"("id") ON DELETE SET NULL ON UPDATE CASCADE;
