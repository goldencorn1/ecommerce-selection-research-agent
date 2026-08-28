-- D4 production migration: explicit tenant context and PostgreSQL RLS.
-- Run this only against a PostgreSQL deployment after reviewing roles.

BEGIN;

ALTER TABLE ecommerce_reports
    ADD COLUMN IF NOT EXISTS tenant_id TEXT;

UPDATE ecommerce_reports
SET tenant_id = owner_id
WHERE tenant_id IS NULL OR tenant_id = '';

ALTER TABLE ecommerce_reports
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ecommerce_reports_tenant_time
    ON ecommerce_reports (tenant_id, created_at DESC);

ALTER TABLE ecommerce_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE ecommerce_reports FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ecommerce_reports_tenant_isolation
    ON ecommerce_reports;

CREATE POLICY ecommerce_reports_tenant_isolation
    ON ecommerce_reports
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

COMMIT;

-- Each transaction/request must set a trusted server-side tenant context:
-- SELECT set_config('app.tenant_id', '<verified-tenant-id>', true);
-- Never derive this value from an unauthenticated client header.
