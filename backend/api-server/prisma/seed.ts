import { PrismaClient, Role } from '@prisma/client';
import * as bcrypt from 'bcrypt';

const prisma = new PrismaClient();

/**
 * Seeds the canonical accounts: admin (role Admin), operator (role Operator),
 * and ilan (role Admin, added at owner's request).
 * This must stay idempotent (upserts, never blind creates) and must never
 * overwrite passwords of existing users — it runs on every container start.
 *
 * Do NOT add fake/demo drivers, vehicles, customers, trips, or invoices here.
 * That was done once, shipped fake data to production on every deploy, and
 * was removed — see CLAUDE.md's "Database & seed rules".
 */
async function main() {
  console.log('🌱 Seeding MERCON default accounts...');

  // Only used to create these two accounts if they don't exist yet. Existing
  // accounts are never touched here — see the `update` blocks below, which
  // intentionally omit `password_hash`.
  const defaultPassword = process.env.SEED_ADMIN_PASSWORD ?? 'password123';
  const password_hash = await bcrypt.hash(defaultPassword, 10);
  const ilan_password_hash = await bcrypt.hash('ilan1234', 10);

  const admin = await prisma.user.upsert({
    where: { username: 'admin' },
    update: {}, // never touch role/password/isActive on an existing account
    create: {
      username: 'admin',
      email: 'admin@mercon.tech',
      phone: '+966500000001',
      password_hash,
      name: 'Mercon Admin',
      role: Role.Admin,
      isActive: true,
    },
  });
  console.log(`  ✓ Admin user: ${admin.username}`);

  const operator = await prisma.user.upsert({
    where: { username: 'operator' },
    update: {},
    create: {
      username: 'operator',
      email: 'operator@mercon.tech',
      phone: '+966500000002',
      password_hash,
      name: 'Mercon Operator',
      role: Role.Operator,
      isActive: true,
    },
  });
  console.log(`  ✓ Operator user: ${operator.username}`);

  const ilan = await prisma.user.upsert({
    where: { username: 'ilan' },
    update: {},
    create: {
      username: 'ilan',
      email: 'ilan@mercon.tech',
      password_hash: ilan_password_hash,
      name: 'Ilan',
      role: Role.Admin,
      isActive: true,
    },
  });
  console.log(`  ✓ Admin user: ${ilan.username}`);

  console.log('✅ Default accounts seeded successfully!');
}

main()
  .catch((e) => {
    console.error('❌ Error during seeding:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
