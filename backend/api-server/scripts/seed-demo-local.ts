/**
 * Local demo data — two years of realistic operating history, for showing the
 * Delay Report with something in it.
 *
 * **This is not the production seed.** `prisma/seed.ts` creates the two real
 * accounts and nothing else; this file creates fake customers, drivers,
 * trucks and trips, and must never touch a real database. Fake demo rows were
 * shipped to production once already and are still listed in PROGRESS.md as
 * needing manual cleanup — hence the guard below rather than a comment asking
 * people to be careful.
 *
 * On localhost it wipes the operational tables first, so it is a clean reset.
 * Against any other database it refuses unless explicitly opted in, never
 * deletes anything, and tags every row so `demo:purge` can remove exactly what
 * it added — for seeding a hosted database that is still empty pre-launch.
 *
 *   npm run seed:demo -w @mercon/api-server
 *   DEMO_ALLOW_REMOTE=yes-i-understand npm run seed:demo   # hosted, additive
 *
 * Data is patterned rather than random, so the report has real findings:
 *   - Khamis -> Edabi degrades steadily across the two years
 *   - Dammam -> Jubail stays reliable (the control)
 *   - summer runs worse; one driver and one truck are clear outliers
 *   - ~55% of delays are Traffic, ~15% are never explained
 */
import { PrismaClient, TripStatus, StopType, DelayReason, Role, AssetType } from '@prisma/client';
import * as bcrypt from 'bcrypt';

import { DEMO_MARKER } from './demo-marker';

const DB = process.env.DATABASE_URL ?? '';

/**
 * Deliberately does NOT include the compose service name `postgres-db`.
 * docker-compose uses that identical hostname on a laptop and on the
 * production VPS, so it says nothing about which database is on the other end
 * — and treating it as "local" would have let a CI job running inside the
 * production API container take the destructive path.
 */
const isLocal = /@(localhost|127\.0\.0\.1|host\.docker\.internal)[:/]/.test(DB);
const REMOTE_OK = process.env.DEMO_ALLOW_REMOTE === 'yes-i-understand';

if (!DB) {
  console.error('\nRefusing to run: DATABASE_URL is unset.\n');
  process.exit(1);
}
if (!isLocal && !REMOTE_OK) {
  console.error(
    '\nRefusing to run against a non-local database.\n\n' +
    `  DATABASE_URL = ${DB.replace(/:[^:@/]*@/, ':***@')}\n\n` +
    'This writes fake customers, drivers, trucks and trips. On a database that\n' +
    'anyone relies on, that is contamination that has to be cleaned out later.\n\n' +
    'If the target really is a pre-launch database with nothing real in it:\n\n' +
    '  DEMO_ALLOW_REMOTE=yes-i-understand npm run seed:demo\n\n' +
    'In that mode nothing is deleted, every row is tagged, and `npm run demo:purge`\n' +
    'removes exactly what was added. Run the purge before real operations begin.\n',
  );
  process.exit(1);
}

/**
 * Deleting is opt-in on its own, never inferred.
 *
 * This used to be derived from the hostname, which was wrong in a way that
 * mattered: production's DATABASE_URL points at `postgres-db`, the same
 * compose service name a laptop uses, so "looks local" and "is safe to wipe"
 * are not the same question. Now the destructive path requires someone to
 * type DEMO_RESET=yes, which nobody does by accident in CI.
 */
const WIPE_FIRST = process.env.DEMO_RESET === 'yes';

const prisma = new PrismaClient();
const MIN = 60_000, HOUR = 60 * MIN, DAY = 24 * HOUR;

// Fixed seed so re-running produces the same history.
let seed = 20260806;
const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
const pick = <T>(a: T[]): T => a[Math.floor(rnd() * a.length)];
const between = (lo: number, hi: number) => lo + rnd() * (hi - lo);

const ROUTES = [
  { from: 'Khamis Sorting Center', to: 'Edabi', hours: 9.5, baseLate: 0.16, degrades: true },
  { from: 'Khamis Sorting Center', to: 'Baish', hours: 6.0, baseLate: 0.14, degrades: false },
  { from: 'Khamis Sorting Center', to: 'Qunfudhah', hours: 7.25, baseLate: 0.13, degrades: false },
  { from: 'Dammam Hub', to: 'Jubail', hours: 4.0, baseLate: 0.04, degrades: false },
  { from: 'Riyadh Depot', to: 'Hail', hours: 8.0, baseLate: 0.10, degrades: false },
  { from: 'Jeddah Port', to: 'Makkah', hours: 3.5, baseLate: 0.07, degrades: false },
  { from: 'Dammam Hub', to: 'Riyadh Depot', hours: 5.0, baseLate: 0.09, degrades: false },
  { from: 'Jeddah Port', to: 'Madinah', hours: 6.5, baseLate: 0.11, degrades: false },
  { from: 'Riyadh Depot', to: 'Buraydah', hours: 4.5, baseLate: 0.08, degrades: false },
  { from: 'Dammam Hub', to: 'Al Ahsa', hours: 3.0, baseLate: 0.06, degrades: false },
];

const REASON_WEIGHTS: [DelayReason | null, number][] = [
  [DelayReason.Traffic, 0.55],
  [null, 0.15],
  [DelayReason.CustomerNotReady, 0.09],
  [DelayReason.VehicleBreakdown, 0.07],
  [DelayReason.SlowLoadingUnloading, 0.06],
  [DelayReason.Documentation, 0.04],
  [DelayReason.Weather, 0.02],
  [DelayReason.RouteBlocked, 0.02],
];
const pickReason = () => {
  let r = rnd();
  for (const [reason, w] of REASON_WEIGHTS) { if (r < w) return reason; r -= w; }
  return DelayReason.Other;
};

const NOTES: Partial<Record<DelayReason, string[]>> = {
  [DelayReason.Traffic]: ['Ring road closed', 'Congestion at the checkpoint', 'Accident on the highway'],
  [DelayReason.VehicleBreakdown]: ['Blown tyre', 'Gearbox fault', 'Overheating, roadside stop'],
  [DelayReason.CustomerNotReady]: ['Warehouse crew unavailable', 'No dock free on arrival'],
  [DelayReason.Weather]: ['Sandstorm, reduced visibility'],
  [DelayReason.Documentation]: ['Waybill correction at origin'],
  [DelayReason.SlowLoadingUnloading]: ['Manual unload, no forklift'],
  [DelayReason.RouteBlocked]: ['Road works diversion'],
};

async function main() {
  console.log(`Seeding demo data into ${DB.replace(/:[^:@/]*@/, ':***@')}`);
  if (WIPE_FIRST) {
    console.log('DEMO_RESET=yes — clearing operational tables first…');
    await prisma.notification.deleteMany({});
    await prisma.invoice.deleteMany({});
    await prisma.tripStop.deleteMany({});
    await prisma.trip.deleteMany({});
    await prisma.maintenanceRecord.deleteMany({});
    await prisma.customer.deleteMany({});
    await prisma.driver.deleteMany({});
    await prisma.vehicle.deleteMany({});
  } else {
    console.log('additive only — nothing will be deleted (set DEMO_RESET=yes to wipe first).');
    console.log(`every row tagged created_by=${DEMO_MARKER}; remove later with: npm run demo:purge`);
  }

  const pw = await bcrypt.hash('demo1234', 10);
  for (const [u, role, name] of [
    ['admin', Role.Admin, 'Admin'], ['operator', Role.Operator, 'Operator'],
  ] as const) {
    await prisma.user.upsert({
      where: { username: u },
      update: { password_hash: pw, isActive: true, role },
      create: { username: u, email: `${u}@mercon.local`, name, role, password_hash: pw },
    });
  }

  const customerNames = ['Bunda Brand', 'Sahal Trading', 'Najd Freight', 'Tihama Foods', 'Asir Cement', 'Red Sea Retail', 'Gulf Steel'];
  const custWeights = [0.26, 0.20, 0.16, 0.12, 0.10, 0.09, 0.07];
  const customers = [];
  for (let i = 0; i < customerNames.length; i++) {
    customers.push(await prisma.customer.create({
      data: { name: customerNames[i], contact_phone: `+96650000${String(i).padStart(4, '0')}`, created_by: DEMO_MARKER },
    }));
  }

  const NAMES = [
    ['Ahmed', 'Ali'], ['Faisal', 'Omar'], ['Yousef', 'Sami'], ['Omar', 'Nasser'], ['Majed', 'Salem'],
    ['Saleh', 'Hadi'], ['Turki', 'Rashid'], ['Nasser', 'Fahd'], ['Bandar', 'Aziz'], ['Khalid', 'Musa'],
    ['Sami', 'Tariq'], ['Rayan', 'Jamal'],
  ];
  const drivers = [];
  for (let i = 0; i < NAMES.length; i++) {
    drivers.push(await prisma.driver.create({
      data: {
        first_name: NAMES[i][0], last_name: NAMES[i][1],
        phone_primary: `+96651000${String(i).padStart(4, '0')}`,
        license_number: `LIC-${2000 + i}`, license_expiry: new Date(Date.now() + 400 * DAY),
        created_by: DEMO_MARKER,
      },
    }));
  }
  const driverRisk = [2.0, 1.0, 1.1, 0.6, 0.9, 1.0, 0.8, 1.3, 0.7, 1.0, 0.9, 1.1];

  const plates = ['9153-PRA', '4471-KLM', '2280-XRT', '8890-TWQ', '3312-BNZ', '7745-MDL', '5061-HSA', '1928-RQT', '6634-JVC', '2077-LMN'];
  const types: AssetType[] = ['Flatbed', 'Reefer', 'Box', 'Tanker'];
  const vehicles = [];
  for (let i = 0; i < plates.length; i++) {
    vehicles.push(await prisma.vehicle.create({
      data: { plate_number: plates[i], asset_type: types[i % 4], capacity_kg: 18000 + i * 800, current_odometer: 90000 + i * 22000, created_by: DEMO_MARKER },
    }));
  }
  const vehicleRisk = [1.0, 0.9, 2.5, 0.8, 1.0, 1.1, 0.9, 1.0, 0.95, 1.05];

  const DAYS = 730;
  const start = new Date(Date.now() - DAYS * DAY);
  const trips: any[] = [], maint: any[] = [];
  let n = 0;

  for (let d = 0; d < DAYS; d++) {
    const day = new Date(start.getTime() + d * DAY);
    if (day.getUTCDay() === 5) continue; // Friday — light day
    const month = day.getUTCMonth();
    const seasonal = month >= 5 && month <= 7 ? 1.5 : month === 11 || month === 0 ? 1.15 : 1.0;
    const progress = d / DAYS;

    for (let t = 0, today = 4 + Math.floor(rnd() * 3); t < today; t++) {
      const route = pick(ROUTES);
      const di = Math.floor(rnd() * drivers.length);
      const vi = Math.floor(rnd() * vehicles.length);
      let r = rnd(), ci = 0;
      for (let i = 0; i < custWeights.length; i++) { if (r < custWeights[i]) { ci = i; break; } r -= custWeights[i]; }

      const depart = new Date(day.getTime() + (5 + Math.floor(rnd() * 10)) * HOUR + Math.floor(rnd() * 60) * MIN);
      const plannedArrival = new Date(depart.getTime() + route.hours * HOUR);
      const lateChance = Math.min(0.85,
        route.baseLate * seasonal * driverRisk[di] * vehicleRisk[vi] * (route.degrades ? 1 + progress * 1.8 : 1));

      let lateMin = 0;
      if (rnd() < lateChance) {
        const s = rnd();
        lateMin = s > 0.93 ? between(240, 480) : s > 0.72 ? between(120, 240) : between(35, 120);
      } else if (rnd() < 0.3) lateMin = between(0, 25);

      const actual = new Date(plannedArrival.getTime() + lateMin * MIN);
      const isLate = lateMin >= 30;
      const reason = isLate ? pickReason() : null;
      const dwell = rnd() < 0.06 ? between(300, 500) : between(20, 110);
      n += 1;

      trips.push({
        ref_id: `TRP-${String(200000 + n)}`,
        customerId: customers[ci].id, driverId: drivers[di].id, vehicleId: vehicles[vi].id,
        cargo_type: pick(['General Goods', 'Refrigerated', 'Dry Bulk', 'Oversized']),
        status: TripStatus.Completed,
        planned_start: depart, actual_start: depart, planned_end: plannedArrival,
        actual_end: new Date(actual.getTime() + dwell * MIN),
        billing_amount: Math.round(between(1800, 6500)),
        created_by: DEMO_MARKER,
        stops: { create: [
          { stop_sequence: 1, stop_type: StopType.Pickup, location_lat: 18.3 + rnd() * 0.01, location_lng: 42.7 + rnd() * 0.01,
            location_name: route.from, planned_arrival: depart, actual_arrival: depart,
            actual_departure: new Date(depart.getTime() + between(20, 60) * MIN) },
          { stop_sequence: 2, stop_type: StopType.Dropoff, location_lat: 17.4 + rnd() * 0.01, location_lng: 42.5 + rnd() * 0.01,
            location_name: route.to, planned_arrival: plannedArrival, actual_arrival: actual,
            actual_departure: new Date(actual.getTime() + dwell * MIN),
            delay_reason: reason, delay_note: reason && NOTES[reason] ? pick(NOTES[reason]!) : null,
            delay_logged_at: reason ? new Date(actual.getTime() + 2 * HOUR) : null },
        ] },
      });

      if (isLate && reason === DelayReason.VehicleBreakdown && rnd() < 0.75) {
        maint.push({
          vehicleId: vehicles[vi].id, service_date: new Date(actual.getTime() + DAY),
          cost: Math.round(between(900, 9000)),
          workshop_name: pick(['Dammam Truck Works', 'Khamis Auto Center', 'Riyadh Fleet Services']),
          maintenance_type: 'Repair', work_done: 'Roadside repair',
          odometer_reading: Math.round(between(100000, 320000)), created_by: DEMO_MARKER,
        });
      }
    }
  }

  console.log(`writing ${trips.length} trips…`);
  for (let i = 0; i < trips.length; i += 60) {
    await Promise.all(trips.slice(i, i + 60).map((data) => prisma.trip.create({ data })));
    if (i % 600 === 0) process.stdout.write(`  ${i}/${trips.length}\r`);
  }
  if (maint.length) await prisma.maintenanceRecord.createMany({ data: maint });

  console.log(
    `\ndone: ${trips.length} trips · ${await prisma.tripStop.count()} stops · ${maint.length} repairs · ` +
    `${customers.length} customers · ${drivers.length} drivers · ${vehicles.length} trucks`,
  );
  console.log('log in as  admin / demo1234  (or operator / demo1234)');
}

main()
  .catch((e) => { console.error(e); process.exit(1); })
  .finally(async () => { await prisma.$disconnect(); });
