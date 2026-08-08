/**
 * Removes everything `seed-demo-local` wrote, and nothing else.
 *
 * Demo rows are stamped with a marker in `created_by`, so this deletes by that
 * marker rather than guessing at names or date ranges — which is what makes it
 * safe to run against a database that has since gained real records. Anything
 * a real operator created is untouched, because it carries a real user id (or
 * null) rather than the marker.
 *
 *   npm run demo:purge -w @mercon/api-server
 *
 * Run this before real operations begin on any database that was seeded for a
 * demo. Prints a count first and does nothing if there is nothing tagged.
 */
import { PrismaClient } from '@prisma/client';
import { DEMO_MARKER } from './demo-marker';

const prisma = new PrismaClient();
const DB = process.env.DATABASE_URL ?? '';

async function main() {
  if (!DB) {
    console.error('Refusing to run: DATABASE_URL is unset.');
    process.exit(1);
  }
  console.log(`Purging demo data from ${DB.replace(/:[^:@/]*@/, ':***@')}`);
  console.log(`marker: created_by = ${DEMO_MARKER}\n`);

  const tagged = { created_by: DEMO_MARKER };

  const [customers, drivers, vehicles, trips, maint] = await Promise.all([
    prisma.customer.count({ where: tagged }),
    prisma.driver.count({ where: tagged }),
    prisma.vehicle.count({ where: tagged }),
    prisma.trip.count({ where: tagged }),
    prisma.maintenanceRecord.count({ where: tagged }),
  ]);

  console.log(`  ${trips} trips · ${customers} customers · ${drivers} drivers · ${vehicles} trucks · ${maint} repairs`);

  if (trips + customers + drivers + vehicles + maint === 0) {
    console.log('\nNothing tagged as demo data. Nothing to do.');
    return;
  }

  // Children before parents: stops and invoices reference trips, and trips
  // reference customers/drivers/vehicles.
  const tripIds = (await prisma.trip.findMany({ where: tagged, select: { id: true } })).map((t) => t.id);

  const stops = await prisma.tripStop.deleteMany({ where: { tripId: { in: tripIds } } });
  const invoices = await prisma.invoice.deleteMany({ where: { tripId: { in: tripIds } } });
  const notes = await prisma.notification.deleteMany({ where: { entity_id: { in: tripIds } } });
  const delTrips = await prisma.trip.deleteMany({ where: tagged });
  const delMaint = await prisma.maintenanceRecord.deleteMany({ where: tagged });
  const delDrivers = await prisma.driver.deleteMany({ where: tagged });
  const delVehicles = await prisma.vehicle.deleteMany({ where: tagged });
  const delCustomers = await prisma.customer.deleteMany({ where: tagged });

  console.log(
    `\nremoved: ${delTrips.count} trips · ${stops.count} stops · ${invoices.count} invoices · ` +
    `${notes.count} notifications · ${delMaint.count} repairs · ${delCustomers.count} customers · ` +
    `${delDrivers.count} drivers · ${delVehicles.count} trucks`,
  );
  console.log('Real records (created_by null or a real user id) were not touched.');
}

main()
  .catch((e) => { console.error(e); process.exit(1); })
  .finally(async () => { await prisma.$disconnect(); });
