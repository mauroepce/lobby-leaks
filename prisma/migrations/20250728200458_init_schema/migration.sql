-- CreateTable
CREATE TABLE "Tenant" (
    "code" TEXT NOT NULL,
    "name" TEXT NOT NULL,

    CONSTRAINT "Tenant_pkey" PRIMARY KEY ("code")
);

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Document" (
    "id" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,
    "uploaderId" TEXT NOT NULL,

    CONSTRAINT "Document_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FundingRecord" (
    "id" TEXT NOT NULL,
    "politician" TEXT NOT NULL,
    "amount" DECIMAL(65,30) NOT NULL,
    "source" TEXT NOT NULL,
    "tenantCode" TEXT NOT NULL,

    CONSTRAINT "FundingRecord_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "FundingRecord_tenantCode_idx" ON "FundingRecord"("tenantCode");

-- AddForeignKey
ALTER TABLE "User" ADD CONSTRAINT "User_tenantCode_fkey" FOREIGN KEY ("tenantCode") REFERENCES "Tenant"("code") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Document" ADD CONSTRAINT "Document_uploaderId_fkey" FOREIGN KEY ("uploaderId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Document" ADD CONSTRAINT "Document_tenantCode_fkey" FOREIGN KEY ("tenantCode") REFERENCES "Tenant"("code") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "FundingRecord" ADD CONSTRAINT "FundingRecord_tenantCode_fkey" FOREIGN KEY ("tenantCode") REFERENCES "Tenant"("code") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Enable & force RLS (default deny while there are no policies)
ALTER TABLE "Tenant"        ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Tenant"        FORCE  ROW LEVEL SECURITY;

ALTER TABLE "User"          ENABLE ROW LEVEL SECURITY;
ALTER TABLE "User"          FORCE  ROW LEVEL SECURITY;

ALTER TABLE "Document"      ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Document"      FORCE  ROW LEVEL SECURITY;

ALTER TABLE "FundingRecord" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "FundingRecord" FORCE  ROW LEVEL SECURITY;
