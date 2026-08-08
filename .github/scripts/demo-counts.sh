#!/usr/bin/env bash
# Prints "<table> <demo-rows> <total-rows>" per line, for the demo-data
# workflow's before/after comparison.
#
# `demo-rows` counts rows stamped with the marker that `seed-demo-local.ts`
# writes into `created_by` (see backend/api-server/scripts/demo-marker.ts).
# Keeping the total alongside it is the point: it shows at a glance how much of
# the table is real data that the purge will not touch.
#
# Read-only. Runs psql inside the postgres container, so it needs no client on
# the runner. Requires POSTGRES_USER in the environment.
set -euo pipefail

MARKER='deadbeef-0000-4000-8000-000000000001'

: "${POSTGRES_USER:?POSTGRES_USER must be set}"

# Prisma models have no @@map, so table names are the model names verbatim and
# must stay double-quoted — unquoted, Postgres would fold them to lowercase and
# fail to find them.
docker exec -i mercon-postgres \
  psql -U "$POSTGRES_USER" -d mercon_db -X -A -t -F' ' -v ON_ERROR_STOP=1 \
  -v marker="$MARKER" <<'SQL'
SELECT 'customers',  count(*) FILTER (WHERE created_by = :'marker'::uuid), count(*) FROM "Customer"
UNION ALL
SELECT 'drivers',    count(*) FILTER (WHERE created_by = :'marker'::uuid), count(*) FROM "Driver"
UNION ALL
SELECT 'vehicles',   count(*) FILTER (WHERE created_by = :'marker'::uuid), count(*) FROM "Vehicle"
UNION ALL
SELECT 'trips',      count(*) FILTER (WHERE created_by = :'marker'::uuid), count(*) FROM "Trip"
UNION ALL
SELECT 'repairs',    count(*) FILTER (WHERE created_by = :'marker'::uuid), count(*) FROM "MaintenanceRecord"
UNION ALL
SELECT 'trip_stops', count(*) FILTER (WHERE created_by = :'marker'::uuid), count(*) FROM "TripStop"
UNION ALL
SELECT 'invoices',   count(*) FILTER (WHERE created_by = :'marker'::uuid), count(*) FROM "Invoice";
SQL
