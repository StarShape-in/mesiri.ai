-- M6.5 identity bridge verification — run after backfill, before 0195.
-- Usage: psql -U mesiri -d mesiri -f scripts/verify_identity_bridge.sql

\echo '=== NULL bridge columns (must be 0 before 0195) ==='
SELECT 'context_organizations' AS tbl, COUNT(*) AS nulls
FROM context_organizations WHERE canonical_organization_id IS NULL
UNION ALL
SELECT 'context_users', COUNT(*) FROM context_users WHERE canonical_user_id IS NULL
UNION ALL
SELECT 'context_projects', COUNT(*) FROM context_projects WHERE canonical_project_id IS NULL
UNION ALL
SELECT 'context_sites', COUNT(*) FROM context_sites WHERE canonical_site_id IS NULL;

\echo '=== Deterministic context IDs (sample) ==='
SELECT id, canonical_organization_id::text
FROM context_organizations
ORDER BY id
LIMIT 5;

\echo '=== Bridge FK integrity (orphan canonical refs) ==='
SELECT COUNT(*) AS orphan_orgs
FROM context_organizations co
LEFT JOIN organizations o ON o.id = co.canonical_organization_id
WHERE co.canonical_organization_id IS NOT NULL AND o.id IS NULL;

SELECT COUNT(*) AS orphan_users
FROM context_users cu
LEFT JOIN users u ON u.id = cu.canonical_user_id
WHERE cu.canonical_user_id IS NOT NULL AND u.id IS NULL;

\echo '=== workflow_instances UUID readiness (pre-0195 string columns) ==='
SELECT COUNT(*) AS non_uuid_org
FROM workflow_instances
WHERE organization_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
   OR user_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
