import { Request, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../index';

export const getMaintenanceRecords = async (req: Request, res: Response) => {
  try {
    const { vehicle_id, status, maintenance_type, search, page = '1', per_page = '50' } = req.query;

    const pageNumber = parseInt(page as string);
    const limit = parseInt(per_page as string);
    const skip = (pageNumber - 1) * limit;

    const whereClause: any = { deletedAt: null };

    if (vehicle_id && vehicle_id !== 'all') {
      whereClause.vehicleId = vehicle_id as string;
    }

    if (status && status !== 'all') {
      whereClause.status = status as string;
    }

    if (maintenance_type && maintenance_type !== 'all') {
      whereClause.maintenance_type = maintenance_type as string;
    }

    if (search) {
      const searchStr = (search as string).trim();
      whereClause.OR = [
        { workshop_name: { contains: searchStr, mode: 'insensitive' } },
        { invoice_number: { contains: searchStr, mode: 'insensitive' } },
        { remarks: { contains: searchStr, mode: 'insensitive' } },
        { work_done: { contains: searchStr, mode: 'insensitive' } },
        { vehicle: { plate_number: { contains: searchStr, mode: 'insensitive' } } },
        { vehicle: { ref_id: { contains: searchStr, mode: 'insensitive' } } },
      ];
    }

    const [records, total, allRecordsForKpi] = await Promise.all([
      prisma.maintenanceRecord.findMany({
        where: whereClause,
        skip,
        take: limit,
        orderBy: [{ start_date: 'desc' }, { service_date: 'desc' }],
        include: {
          vehicle: {
            select: {
              id: true,
              plate_number: true,
              ref_id: true,
              asset_type: true,
              status: true,
              current_odometer: true,
            },
          },
        },
      }),
      prisma.maintenanceRecord.count({ where: whereClause }),
      prisma.maintenanceRecord.findMany({
        where: { deletedAt: null, ...(vehicle_id && vehicle_id !== 'all' ? { vehicleId: vehicle_id as string } : {}) },
        select: { cost: true, status: true, maintenance_type: true },
      }),
    ]);

    const totalCost = allRecordsForKpi.reduce((sum, r) => sum + (r.cost || 0), 0);
    const activeCount = allRecordsForKpi.filter((r) => r.status === 'In_Progress' || r.status === 'In Progress').length;
    const scheduledCount = allRecordsForKpi.filter((r) => r.status === 'Scheduled').length;
    const completedCount = allRecordsForKpi.filter((r) => r.status === 'Completed').length;
    const renewalCost = allRecordsForKpi
      .filter((r) => r.maintenance_type === 'Renewal')
      .reduce((sum, r) => sum + (r.cost || 0), 0);

    res.json({
      success: true,
      data: records,
      kpis: {
        total_cost: totalCost,
        active_count: activeCount,
        scheduled_count: scheduledCount,
        completed_count: completedCount,
        renewal_cost: renewalCost,
      },
      meta: {
        page: pageNumber,
        per_page: limit,
        total,
        total_pages: Math.ceil(total / limit),
      },
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: { code: 'SERVER_ERROR', message: 'Failed to fetch maintenance records' },
    });
  }
};

export const getMaintenanceRecordById = async (req: Request, res: Response) => {
  try {
    const recordId = req.params.id as string;
    const record = await prisma.maintenanceRecord.findUnique({
      where: { id: recordId },
      include: {
        vehicle: true,
      },
    });

    if (!record || record.deletedAt) {
      return res.status(404).json({
        success: false,
        error: { code: 'NOT_FOUND', message: 'Maintenance record not found' },
      });
    }

    const documents = await prisma.document.findMany({
      where: { entity_type: 'MaintenanceRecord', entity_id: record.id, deletedAt: null },
    });

    res.json({
      success: true,
      data: {
        ...record,
        documents,
      },
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: { code: 'SERVER_ERROR', message: 'Failed to fetch maintenance record details' },
    });
  }
};

const maintenanceSchema = z.object({
  vehicle_id: z.string().uuid(),
  workshop_name: z.string().min(1, 'Workshop name is required'),
  workshop_contact: z.string().optional().nullable(),
  maintenance_type: z.enum(['Routine', 'Repair', 'Inspection', 'Renewal', 'Emergency']),
  status: z.enum(['Scheduled', 'In_Progress', 'Completed', 'Cancelled']).default('Completed'),
  start_date: z.string().or(z.date()).optional(),
  end_date: z.string().or(z.date()).optional().nullable(),
  service_date: z.string().or(z.date()).optional(),
  work_done: z.string().optional().nullable(),
  odometer_reading: z.union([z.string(), z.number()]).transform((v) => parseFloat(v as string)),
  cost: z.union([z.string(), z.number()]).optional().transform((v) => (v ? parseFloat(v as string) : 0)),
  invoice_number: z.string().optional().nullable(),
  invoice_url: z.string().optional().nullable(),
  next_service_due: z.string().or(z.date()).optional().nullable(),
  remarks: z.string().optional().nullable(),
});

export const createMaintenanceRecord = async (req: Request, res: Response) => {
  try {
    const parseResult = maintenanceSchema.safeParse(req.body);
    if (!parseResult.success) {
      return res.status(400).json({
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: parseResult.error.issues[0].message,
          details: parseResult.error.format(),
        },
      });
    }

    const {
      vehicle_id,
      workshop_name,
      workshop_contact,
      maintenance_type,
      status,
      start_date,
      end_date,
      service_date,
      work_done,
      odometer_reading,
      cost,
      invoice_number,
      invoice_url,
      next_service_due,
      remarks,
    } = parseResult.data;

    const startDateVal = start_date ? new Date(start_date) : service_date ? new Date(service_date) : new Date();
    const serviceDateVal = service_date ? new Date(service_date) : startDateVal;
    const endDateVal = end_date ? new Date(end_date) : status === 'Completed' ? serviceDateVal : null;

    const record = await prisma.maintenanceRecord.create({
      data: {
        vehicleId: vehicle_id,
        workshop_name,
        workshop_contact: workshop_contact || null,
        maintenance_type,
        status: status || 'Completed',
        start_date: startDateVal,
        end_date: endDateVal,
        service_date: serviceDateVal,
        work_done: work_done || null,
        odometer_reading,
        cost: cost || 0,
        invoice_number: invoice_number || null,
        invoice_url: invoice_url || null,
        next_service_due: next_service_due ? new Date(next_service_due) : null,
        remarks: remarks || null,
        created_by: (req as any).user?.id,
      },
      include: {
        vehicle: true,
      },
    });

    // If status is In_Progress, optionally update vehicle status to Maintenance
    if (status === 'In_Progress') {
      await prisma.vehicle.update({
        where: { id: vehicle_id },
        data: { status: 'Maintenance' },
      });
    } else if (status === 'Completed') {
      // Update vehicle odometer reading if higher
      const vehicle = await prisma.vehicle.findUnique({ where: { id: vehicle_id } });
      if (vehicle && odometer_reading > vehicle.current_odometer) {
        await prisma.vehicle.update({
          where: { id: vehicle_id },
          data: { current_odometer: odometer_reading },
        });
      }
    }

    res.status(201).json({ success: true, data: record });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: { code: 'SERVER_ERROR', message: 'Failed to create maintenance record' },
    });
  }
};

export const updateMaintenanceRecord = async (req: Request, res: Response) => {
  try {
    const recordId = req.params.id as string;
    const updateSchema = maintenanceSchema.partial();
    const parseResult = updateSchema.safeParse(req.body);

    if (!parseResult.success) {
      return res.status(400).json({
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: parseResult.error.issues[0].message,
          details: parseResult.error.format(),
        },
      });
    }

    const existing = await prisma.maintenanceRecord.findUnique({ where: { id: recordId } });
    if (!existing || existing.deletedAt) {
      return res.status(404).json({
        success: false,
        error: { code: 'NOT_FOUND', message: 'Maintenance record not found' },
      });
    }

    const data: any = { ...parseResult.data };
    if (data.start_date) data.start_date = new Date(data.start_date);
    if (data.end_date) data.end_date = new Date(data.end_date);
    if (data.service_date) data.service_date = new Date(data.service_date);
    if (data.next_service_due) data.next_service_due = new Date(data.next_service_due);
    if (data.vehicle_id) {
      data.vehicleId = data.vehicle_id;
      delete data.vehicle_id;
    }

    const updated = await prisma.maintenanceRecord.update({
      where: { id: recordId },
      data: {
        ...data,
        updated_by: (req as any).user?.id,
      },
      include: {
        vehicle: true,
      },
    });

    // Handle Vehicle status transitions and odometer updates
    if (updated.vehicleId) {
      if (data.status === 'In_Progress') {
        await prisma.vehicle.update({
          where: { id: updated.vehicleId },
          data: { status: 'Maintenance' },
        });
      } else if (data.status === 'Completed' || data.status === 'Cancelled') {
        const activeMaintenance = await prisma.maintenanceRecord.count({
          where: {
            vehicleId: updated.vehicleId,
            status: 'In_Progress',
            deletedAt: null,
            id: { not: recordId },
          },
        });
        if (activeMaintenance === 0) {
          await prisma.vehicle.update({
            where: { id: updated.vehicleId },
            data: { status: 'Available' },
          });
        }
      }

      if (data.odometer_reading && updated.vehicle) {
        if (data.odometer_reading > updated.vehicle.current_odometer) {
          await prisma.vehicle.update({
            where: { id: updated.vehicleId },
            data: { current_odometer: data.odometer_reading },
          });
        }
      }
    }

    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: { code: 'SERVER_ERROR', message: 'Failed to update maintenance record' },
    });
  }
};

export const deleteMaintenanceRecord = async (req: Request, res: Response) => {
  try {
    const recordId = req.params.id as string;
    const existing = await prisma.maintenanceRecord.findUnique({ where: { id: recordId } });

    if (!existing || existing.deletedAt) {
      return res.status(404).json({
        success: false,
        error: { code: 'NOT_FOUND', message: 'Maintenance record not found' },
      });
    }

    await prisma.maintenanceRecord.update({
      where: { id: recordId },
      data: {
        deletedAt: new Date(),
        deleted_by: (req as any).user?.id,
      },
    });

    res.json({ success: true, message: 'Maintenance record deleted successfully' });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: { code: 'SERVER_ERROR', message: 'Failed to delete maintenance record' },
    });
  }
};
