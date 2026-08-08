import { Request, Response } from 'express';
import { prisma } from '../index';
import { generateRefId } from '../utils/refId';
import { AssetStatus, AssetType } from '@prisma/client';

export const getVehicles = async (req: Request, res: Response) => {
  try {
    const { status, search, page = '1', per_page = '20' } = req.query;
    
    const pageNumber = parseInt(page as string);
    const limit = parseInt(per_page as string);
    const skip = (pageNumber - 1) * limit;

    const whereClause: any = { deletedAt: null };
    if (status) {
      whereClause.status = status as AssetStatus;
    }
    if (search) {
      whereClause.plate_number = { contains: search as string, mode: 'insensitive' };
    }

    const [vehicles, total] = await Promise.all([
      prisma.vehicle.findMany({
        where: whereClause,
        skip,
        take: limit,
        orderBy: { createdAt: 'desc' },
        include: {
          trips: {
            where: {
              deletedAt: null,
              status: {
                in: ['Dispatched', 'AtPickup', 'InTransit', 'AtDelivery']
              }
            },
            include: {
              driver: true
            },
            take: 1
          }
        }
      }),
      prisma.vehicle.count({ where: whereClause })
    ]);

    res.json({
      success: true,
      data: vehicles,
      meta: {
        page: pageNumber,
        per_page: limit,
        total,
        total_pages: Math.ceil(total / limit)
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch vehicles' } });
  }
};

export const getVehicleById = async (req: Request, res: Response) => {
  try {
    const vehicle = await prisma.vehicle.findUnique({
      where: { id: req.params.id as string, deletedAt: null }
    });

    if (!vehicle) {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Vehicle not found' } });
    }

    // Fetch documents manually because of polymorphic relation
    const documents = await prisma.document.findMany({
      where: { entity_type: 'Vehicle', entity_id: vehicle.id, deletedAt: null }
    });

    res.json({ success: true, data: { ...vehicle, documents } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch vehicle' } });
  }
};

export const createVehicle = async (req: Request, res: Response) => {
  try {
    const {
      plate_number,
      asset_type,
      capacity_kg,
      trailer_number,
      trailer_type,
      trailer_capacity_kg,
      gps_device_id,
      icces_device_id
    } = req.body;

    const ref_id = await generateRefId('TRK', () =>
      prisma.vehicle.findMany({ select: { ref_id: true } }));

    const vehicle = await prisma.vehicle.create({
      data: {
        ref_id,
        plate_number,
        asset_type: asset_type as AssetType,
        capacity_kg,
        trailer_number,
        trailer_type: trailer_type ? (trailer_type as AssetType) : null,
        trailer_capacity_kg,
        gps_device_id,
        icces_device_id,
        created_by: (req as any).user?.id
      }
    });

    res.status(201).json({ success: true, data: vehicle });
  } catch (error: any) {
    if (error.code === 'P2002') {
      return res.status(400).json({ success: false, error: { code: 'DUPLICATE', message: 'Plate number already exists' } });
    }
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to create vehicle' } });
  }
};

export const updateVehicle = async (req: Request, res: Response) => {
  try {
    const updated = await prisma.vehicle.update({
      where: { id: req.params.id as string },
      data: {
        ...req.body,
        asset_type: req.body.asset_type ? (req.body.asset_type as AssetType) : undefined,
        trailer_type: req.body.trailer_type ? (req.body.trailer_type as AssetType) : undefined,
        updated_by: (req as any).user?.id
      }
    });
    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to update vehicle' } });
  }
};

export const deleteVehicle = async (req: Request, res: Response) => {
  try {
    await prisma.vehicle.update({
      where: { id: req.params.id as string },
      data: {
        deletedAt: new Date(),
        isActive: false,
        deleted_by: (req as any).user?.id
      }
    });
    res.json({ success: true, data: { message: 'Vehicle deleted successfully' } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to delete vehicle' } });
  }
};


export const bulkDeleteVehicles = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'No IDs provided' } });
    }

    await prisma.vehicle.updateMany({
      where: { id: { in: ids } },
      data: {
        deletedAt: new Date(),
        isActive: false,
        deleted_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully deleted ${ids.length} vehicles` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk delete vehicles` } });
  }
};

export const bulkUpdateVehicleStatus = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids, status } = req.body;

    if (!Array.isArray(ids) || ids.length === 0 || !status) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'IDs and status are required' } });
    }

    await prisma.vehicle.updateMany({
      where: { id: { in: ids } },
      data: {
        status: status as AssetStatus,
        updated_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully updated ${ids.length} vehicles` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk update vehicles` } });
  }
};

export const getVehicleFinancials = async (req: Request, res: Response) => {
  try {
    const vehicleId = req.params.id as string;
    const vehicle = await prisma.vehicle.findUnique({
      where: { id: vehicleId, deletedAt: null },
    });

    if (!vehicle) {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Vehicle not found' } });
    }

    const trips = await prisma.trip.findMany({
      where: { vehicleId, deletedAt: null },
      orderBy: { createdAt: 'desc' },
      include: {
        customer: { select: { name: true } },
        invoices: { where: { deletedAt: null } },
      },
    });

    const maintenanceRecords = await prisma.maintenanceRecord.findMany({
      where: { vehicleId, deletedAt: null },
      orderBy: [{ start_date: 'desc' }, { service_date: 'desc' }],
    });

    let totalIncome = 0;
    const tripBreakdown = trips.map((t) => {
      const invoice = t.invoices[0];
      const income = (t.billing_amount && t.billing_amount > 0)
        ? t.billing_amount
        : (invoice?.total_amount && invoice.total_amount > 0)
          ? invoice.total_amount
          : (t.trip_charges || 0);
      if (t.status === 'Completed' || t.status === 'Invoiced') {
        totalIncome += income;
      }
      return {
        id: t.id,
        ref_id: t.ref_id,
        status: t.status,
        customer_name: t.customer?.name || 'N/A',
        cargo_type: t.cargo_type,
        date: t.actual_end || t.actual_start || t.createdAt,
        income,
      };
    });

    const totalMaintenanceExpense = maintenanceRecords.reduce((sum, m) => sum + (m.cost || 0), 0);
    const renewalExpenses = maintenanceRecords
      .filter((m) => m.maintenance_type === 'Renewal')
      .reduce((sum, m) => sum + (m.cost || 0), 0);

    const totalExpenses = totalMaintenanceExpense;
    const netProfit = totalIncome - totalExpenses;
    const marginPercent = totalIncome > 0 ? Math.round((netProfit / totalIncome) * 1000) / 10 : 0;

    res.json({
      success: true,
      data: {
        vehicle_id: vehicle.id,
        plate_number: vehicle.plate_number,
        ref_id: vehicle.ref_id,
        asset_type: vehicle.asset_type,
        summary: {
          total_income: totalIncome,
          total_expenses: totalExpenses,
          maintenance_expenses: totalMaintenanceExpense,
          renewal_expenses: renewalExpenses,
          net_profit: netProfit,
          margin_percent: marginPercent,
          completed_trips_count: trips.filter((t) => t.status === 'Completed' || t.status === 'Invoiced').length,
          total_maintenance_count: maintenanceRecords.length,
        },
        income_sources: tripBreakdown,
        expense_records: maintenanceRecords,
      },
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch vehicle financial report' } });
  }
};

