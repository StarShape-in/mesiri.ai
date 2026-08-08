import { Request, Response } from 'express';
import { logger } from '../utils/logger';
import { prisma } from '../index';
import { TripStatus, InvoiceStatus, DriverStatus, AssetStatus } from '@prisma/client';

/* ─── Dashboard summary KPIs ──────────────────────────────────────────────── */
export const getSummary = async (req: Request, res: Response) => {
  try {
    const now = new Date();
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const startOfLastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const endOfLastMonth = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59);

    const [
      totalTripsThisMonth,
      totalTripsLastMonth,
      activeDrivers,
      availableVehicles,
      onTripVehicles,
      revenueThisMonth,
      revenueLastMonth,
      tripsByStatus,
      docsExpiringIn30Days,
      recentMonthlyRevenue
    ] = await Promise.all([
      // Total trips this month
      prisma.trip.count({ where: { deletedAt: null, createdAt: { gte: startOfMonth } } }),
      // Total trips last month (for delta)
      prisma.trip.count({ where: { deletedAt: null, createdAt: { gte: startOfLastMonth, lte: endOfLastMonth } } }),
      // Active drivers
      prisma.driver.count({ where: { deletedAt: null, isActive: true, status: DriverStatus.Available } }),
      // Available vehicles
      prisma.vehicle.count({ where: { deletedAt: null, isActive: true, status: AssetStatus.Available } }),
      // On-trip vehicles
      prisma.vehicle.count({ where: { deletedAt: null, isActive: true, status: AssetStatus.OnTrip } }),
      // Revenue this month (paid invoices)
      prisma.invoice.aggregate({
        where: { deletedAt: null, status: InvoiceStatus.Paid, createdAt: { gte: startOfMonth } },
        _sum: { total_amount: true }
      }),
      // Revenue last month
      prisma.invoice.aggregate({
        where: { deletedAt: null, status: InvoiceStatus.Paid, createdAt: { gte: startOfLastMonth, lte: endOfLastMonth } },
        _sum: { total_amount: true }
      }),
      // Trip distribution by status
      prisma.trip.groupBy({
        by: ['status'],
        where: { deletedAt: null, createdAt: { gte: startOfMonth } },
        _count: { status: true }
      }),
      // Documents expiring within 30 days
      prisma.document.count({
        where: {
          deletedAt: null,
          expiry_date: { gte: now, lte: new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000) }
        }
      }),
      // Monthly revenue for the last 6 months (for chart)
      prisma.$queryRaw<{ month: string; revenue: number }[]>`
        SELECT
          TO_CHAR(DATE_TRUNC('month', "createdAt"), 'Mon') AS month,
          COALESCE(SUM("total_amount"), 0) AS revenue
        FROM "Invoice"
        WHERE "deletedAt" IS NULL
          AND status = 'Paid'
          AND "createdAt" >= NOW() - INTERVAL '6 months'
        GROUP BY DATE_TRUNC('month', "createdAt")
        ORDER BY DATE_TRUNC('month', "createdAt") ASC
      `
    ]);

    const revenueNow = revenueThisMonth._sum.total_amount ?? 0;
    const revenuePrev = revenueLastMonth._sum.total_amount ?? 0;
    const tripsDelta = totalTripsLastMonth > 0
      ? Math.round(((totalTripsThisMonth - totalTripsLastMonth) / totalTripsLastMonth) * 100)
      : 0;
    const revenueDelta = revenuePrev > 0
      ? Math.round(((revenueNow - revenuePrev) / revenuePrev) * 100)
      : 0;

    // Build status distribution map
    const statusMap: Record<string, number> = {};
    tripsByStatus.forEach((row) => { statusMap[row.status] = row._count.status; });

    res.json({
      success: true,
      data: {
        kpis: {
          total_trips: { value: totalTripsThisMonth, delta: tripsDelta },
          active_drivers: { value: activeDrivers, delta: null },
          fleet_available: { value: availableVehicles, delta: null },
          fleet_on_trip: { value: onTripVehicles, delta: null },
          revenue_this_month: { value: revenueNow, delta: revenueDelta },
          docs_expiring_soon: { value: docsExpiringIn30Days, delta: null }
        },
        trip_status_distribution: statusMap,
        monthly_revenue_chart: recentMonthlyRevenue
      }
    });
  } catch (error) {
    logger.error({ err: error }, 'Reports summary error:');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to generate summary report' } });
  }
};

/* ─── Fleet performance ───────────────────────────────────────────────────── */
export const getFleetPerformance = async (req: Request, res: Response) => {
  try {
    const { startDate, endDate, page = '1', per_page = '10' } = req.query;
    
    const pageNum = parseInt(page as string, 10);
    const limitNum = parseInt(per_page as string, 10);
    const skip = (pageNum - 1) * limitNum;

    // Build trips condition based on date filters
    const tripsCondition: any = { deletedAt: null };
    if (startDate) {
      tripsCondition.createdAt = { ...tripsCondition.createdAt, gte: new Date(startDate as string) };
    }
    if (endDate) {
      const end = new Date(endDate as string);
      end.setHours(23, 59, 59, 999);
      tripsCondition.createdAt = { ...tripsCondition.createdAt, lte: end };
    }

    const [total, vehicles] = await Promise.all([
      prisma.vehicle.count({ where: { deletedAt: null } }),
      prisma.vehicle.findMany({
        where: { deletedAt: null },
        skip,
        take: limitNum,
        include: {
          trips: {
            where: tripsCondition,
            select: { status: true, actual_start: true, actual_end: true }
          },
          maintenanceRecords: {
            where: { deletedAt: null },
            select: { cost: true, service_date: true }
          }
        }
      })
    ]);

    const data = vehicles.map((v) => ({
      id: v.id,
      ref_id: v.ref_id,
      plate_number: v.plate_number,
      status: v.status,
      total_trips: v.trips.length,
      completed_trips: v.trips.filter((t) => t.status === TripStatus.Completed).length,
      odometer: v.current_odometer,
      maintenance_cost: v.maintenanceRecords.reduce((sum, m) => sum + m.cost, 0)
    }));

    res.json({
      success: true,
      data,
      meta: {
        total,
        page: pageNum,
        limit: limitNum,
        total_pages: Math.ceil(total / limitNum)
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to get fleet performance' } });
  }
};

/* ─── Driver performance ──────────────────────────────────────────────────── */
export const getDriverPerformance = async (req: Request, res: Response) => {
  try {
    const { startDate, endDate, page = '1', per_page = '10' } = req.query;
    
    const pageNum = parseInt(page as string, 10);
    const limitNum = parseInt(per_page as string, 10);
    const skip = (pageNum - 1) * limitNum;

    // Build trips condition based on date filters
    const tripsCondition: any = { deletedAt: null };
    if (startDate) {
      tripsCondition.createdAt = { ...tripsCondition.createdAt, gte: new Date(startDate as string) };
    }
    if (endDate) {
      const end = new Date(endDate as string);
      end.setHours(23, 59, 59, 999);
      tripsCondition.createdAt = { ...tripsCondition.createdAt, lte: end };
    }

    const [total, drivers] = await Promise.all([
      prisma.driver.count({ where: { deletedAt: null } }),
      prisma.driver.findMany({
        where: { deletedAt: null },
        skip,
        take: limitNum,
        include: {
          trips: {
            where: tripsCondition,
            select: { status: true, actual_start: true, actual_end: true, planned_start: true, planned_end: true }
          }
        }
      })
    ]);

    const data = drivers.map((d) => {
      const completed = d.trips.filter((t) => t.status === TripStatus.Completed);
      return {
        id: d.id,
        ref_id: d.ref_id,
        name: `${d.first_name} ${d.last_name}`,
        status: d.status,
        total_trips: d.trips.length,
        completed_trips: completed.length,
        ai_risk_score: d.ai_risk_score
      };
    });

    res.json({
      success: true,
      data,
      meta: {
        total,
        page: pageNum,
        limit: limitNum,
        total_pages: Math.ceil(total / limitNum)
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to get driver performance' } });
  }
};

/* ─── Revenue report ──────────────────────────────────────────────────────── */
export const getRevenueReport = async (req: Request, res: Response) => {
  try {
    const { months = '6' } = req.query;
    const monthCount = parseInt(months as string);

    const rows = await prisma.$queryRaw<{ month: string; revenue: number; count: number }[]>`
      SELECT
        TO_CHAR(DATE_TRUNC('month', "createdAt"), 'Mon YYYY') AS month,
        COALESCE(SUM("total_amount"), 0)::float8 AS revenue,
        COUNT(*)::int AS count
      FROM "Invoice"
      WHERE "deletedAt" IS NULL
        AND status = 'Paid'
        AND "createdAt" >= NOW() - (${monthCount} || ' months')::INTERVAL
      GROUP BY DATE_TRUNC('month', "createdAt")
      ORDER BY DATE_TRUNC('month', "createdAt") ASC
    `;

    const totalRevenue = await prisma.invoice.aggregate({
      where: { deletedAt: null, status: InvoiceStatus.Paid },
      _sum: { total_amount: true },
      _count: true
    });

    // Outstanding = issued but not yet settled (Pending + Overdue)
    const outstanding = await prisma.invoice.aggregate({
      where: { deletedAt: null, status: { in: [InvoiceStatus.Pending, InvoiceStatus.Overdue] } },
      _sum: { total_amount: true }
    });

    // Top customers by paid revenue
    const grouped = await prisma.invoice.groupBy({
      by: ['customerId'],
      where: { deletedAt: null, status: InvoiceStatus.Paid },
      _sum: { total_amount: true },
      orderBy: { _sum: { total_amount: 'desc' } },
      take: 5
    });
    const customers = await prisma.customer.findMany({
      where: { id: { in: grouped.map((g) => g.customerId) } },
      select: { id: true, name: true }
    });
    const nameById = new Map(customers.map((c) => [c.id, c.name]));
    const top_customers = grouped.map((g) => ({
      name: nameById.get(g.customerId) ?? 'Unknown',
      value: g._sum.total_amount ?? 0
    }));

    const paidCount = totalRevenue._count;
    const paidTotal = totalRevenue._sum.total_amount ?? 0;

    res.json({
      success: true,
      data: {
        monthly_breakdown: rows,
        total_all_time: paidTotal,
        outstanding_total: outstanding._sum.total_amount ?? 0,
        paid_invoice_count: paidCount,
        avg_per_invoice: paidCount > 0 ? paidTotal / paidCount : 0,
        top_customers
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to get revenue report' } });
  }
};

/* ─── Custom report ───────────────────────────────────────────────────────── */
export const getCustomReport = async (req: Request, res: Response) => {
  try {
    const { startDate, endDate, customerId } = req.query;
    
    const whereClause: any = { deletedAt: null };
    
    if (startDate) {
      whereClause.createdAt = { ...whereClause.createdAt, gte: new Date(startDate as string) };
    }
    if (endDate) {
      // Add time to cover the whole end day
      const end = new Date(endDate as string);
      end.setHours(23, 59, 59, 999);
      whereClause.createdAt = { ...whereClause.createdAt, lte: end };
    }
    if (customerId && customerId !== 'all') {
      whereClause.customerId = customerId;
    }

    const [
      totalTrips,
      tripsByStatus,
      recentTrips
    ] = await Promise.all([
      prisma.trip.count({ where: whereClause }),
      prisma.trip.groupBy({
        by: ['status'],
        where: whereClause,
        _count: { status: true }
      }),
      prisma.trip.findMany({
        where: whereClause,
        orderBy: { createdAt: 'desc' },
        take: 500, // Increase limit for ledger exports
        include: {
          customer: { select: { name: true } },
          driver: { select: { first_name: true, last_name: true, phone_primary: true } },
          vehicle: { select: { plate_number: true, capacity_kg: true, asset_type: true } },
          stops: { orderBy: { stop_sequence: 'asc' } },
          invoices: true,
        }
      })
    ]);

    // For revenue, we filter invoices based on the same criteria
    const invoiceWhere: any = { deletedAt: null, status: InvoiceStatus.Paid };
    if (startDate) invoiceWhere.createdAt = { ...invoiceWhere.createdAt, gte: new Date(startDate as string) };
    if (endDate) {
      const end = new Date(endDate as string);
      end.setHours(23, 59, 59, 999);
      invoiceWhere.createdAt = { ...invoiceWhere.createdAt, lte: end };
    }
    if (customerId && customerId !== 'all') invoiceWhere.customerId = customerId;

    const totalRevenue = await prisma.invoice.aggregate({
      where: invoiceWhere,
      _sum: { total_amount: true }
    });

    const statusMap: Record<string, number> = {};
    tripsByStatus.forEach((row) => { statusMap[row.status] = row._count.status; });

    res.json({
      success: true,
      data: {
        kpis: {
          total_trips: totalTrips,
          total_revenue: totalRevenue._sum.total_amount ?? 0,
        },
        trip_status_distribution: statusMap,
        trips: recentTrips.map(t => {
          const dropoff = t.stops.find(s => s.stop_type === 'Dropoff');
          const invoice = t.invoices[0];
          const billing = t.billing_amount ?? (invoice?.subtotal || 0);
          const totalAmt = invoice?.total_amount ?? (billing + t.waiting_labor_charges + t.additional_stop_charges);
          const balance = totalAmt - t.trip_charges;
          const vehicleTypeLabel = t.vehicle ? `${(t.vehicle.capacity_kg / 1000).toFixed(0)} TON (${t.vehicle.asset_type})` : 'N/A';

          return {
            id: t.id,
            ref_id: t.ref_id,
            date: t.actual_start || t.createdAt,
            driver: t.driver ? `${t.driver.first_name} ${t.driver.last_name}` : 'N/A',
            driver_phone: t.driver?.phone_primary || 'N/A',
            vehicle: t.vehicle?.plate_number || 'N/A',
            vehicle_type: vehicleTypeLabel,
            carrier_name: t.carrier_name || 'MERCON LOGISTICS',
            customer: t.customer?.name || 'N/A',
            receiver: dropoff ? `Dropoff Stop ${dropoff.stop_sequence}` : 'N/A',
            waiting_labor_charges: t.waiting_labor_charges,
            additional_stop_charges: t.additional_stop_charges,
            billing_amount: billing,
            total_amount: totalAmt,
            trip_charges: t.trip_charges,
            balance_amount: balance,
            company_name: t.customer?.name || 'MERCON',
            status: t.status,
            is_post_trip_settled: t.is_post_trip_settled
          };
        })
      }
    });
  } catch (error) {
    logger.error({ err: error }, 'Custom report error:');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to generate custom report' } });
  }
};

