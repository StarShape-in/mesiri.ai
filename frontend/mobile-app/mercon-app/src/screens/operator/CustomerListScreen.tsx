/**
 * Route entry for the Operator Customers screen — implementation lives in the
 * customers feature module (src/features/customers).
 *
 * Kept as a re-export so any deep import of this path keeps resolving, mirroring
 * how DriverListScreen was handled when the drivers list moved into its feature.
 */
export { default } from '@/features/customers/screens/CustomersScreen';
