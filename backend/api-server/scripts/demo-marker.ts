/**
 * Stamped into `created_by` on every row the demo seeder writes.
 *
 * Not a real user id — nothing references it and it never surfaces in the UI —
 * but it is what lets `demo:purge` delete demo data exactly, instead of
 * guessing at names or date ranges and risking a real record.
 *
 * Lives in its own module so the purge script can read it without importing
 * the seeder, whose safety guard runs (and can exit) at module load.
 */
export const DEMO_MARKER = 'deadbeef-0000-4000-8000-000000000001';
