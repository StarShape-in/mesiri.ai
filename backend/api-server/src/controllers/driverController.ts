import { Request, Response } from 'express';
import { prisma } from '../index';
import { generateRefId } from '../utils/refId';
import { DriverStatus } from '@prisma/client';
import bcrypt from 'bcrypt';

export const getDrivers = async (req: Request, res: Response) => {
  try {
    const { status, search, page = '1', per_page = '20' } = req.query;
    
    const pageNumber = parseInt(page as string);
    const limit = parseInt(per_page as string);
    const skip = (pageNumber - 1) * limit;

    const whereClause: any = { deletedAt: null };
    if (status) {
      whereClause.status = status as DriverStatus;
    }
    if (search) {
      whereClause.first_name = { contains: search as string, mode: 'insensitive' };
    }

    const [drivers, total] = await Promise.all([
      prisma.driver.findMany({
        where: whereClause,
        skip,
        take: limit,
        orderBy: { first_name: 'asc' },
        include: {
          trips: {
            where: {
              deletedAt: null,
              status: {
                in: ['Dispatched', 'AtPickup', 'InTransit', 'AtDelivery']
              }
            },
            include: {
              vehicle: true
            },
            take: 1
          }
        }
      }),
      prisma.driver.count({ where: whereClause })
    ]);

    res.json({
      success: true,
      data: drivers,
      meta: {
        page: pageNumber,
        per_page: limit,
        total,
        total_pages: Math.ceil(total / limit),
        has_next: (skip + limit) < total,
        has_prev: pageNumber > 1
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch drivers' } });
  }
};

export const getDriverById = async (req: Request, res: Response) => {
  try {
    const driver = await prisma.driver.findUnique({
      where: { id: req.params.id as string, deletedAt: null },
      include: { trips: { take: 5, orderBy: { createdAt: 'desc' } } }
    });

    if (!driver) {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Driver not found' } });
    }

    const documents = await prisma.document.findMany({
      where: { entity_type: 'Driver', entity_id: driver.id, deletedAt: null }
    });

    res.json({ success: true, data: { ...driver, documents } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch driver' } });
  }
};

export const createDriver = async (req: Request, res: Response) => {
  try {
    const { first_name, last_name, phone_primary, license_number, license_expiry } = req.body; // validated by createDriverBody

    const ref_id = await generateRefId('DRV', () =>
      prisma.driver.findMany({ select: { ref_id: true } }));

    const newDriver = await prisma.driver.create({
      data: {
        ref_id,
        first_name,
        last_name,
        phone_primary,
        license_number,
        license_expiry: new Date(license_expiry),
        created_by: (req as any).user?.id
      }
    });

    res.status(201).json({ success: true, data: newDriver });
  } catch (error: any) {
    if (error.code === 'P2002') {
      return res.status(400).json({ success: false, error: { code: 'DUPLICATE_ENTRY', message: 'Phone number already exists' } });
    }
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to create driver' } });
  }
};

export const updateDriver = async (req: Request, res: Response) => {
  try {
    const updatedDriver = await prisma.driver.update({
      where: { id: req.params.id as string },
      data: {
        ...req.body,
        updated_by: (req as any).user?.id
      }
    });

    res.json({ success: true, data: updatedDriver });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to update driver' } });
  }
};

export const deleteDriver = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { password } = req.body;

    if (!password) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'Password is required to confirm deletion' } });
    }

    const user = await prisma.user.findUnique({ where: { id: userId } });
    if (!user || !user.password_hash) {
      return res.status(401).json({ success: false, error: { code: 'UNAUTHORIZED', message: 'User not found or missing password' } });
    }

    const isValid = await bcrypt.compare(password, user.password_hash);
    if (!isValid) {
      return res.status(401).json({ success: false, error: { code: 'INVALID_CREDENTIALS', message: 'Incorrect password' } });
    }

    await prisma.driver.update({
      where: { id: req.params.id as string },
      data: {
        deletedAt: new Date(),
        isActive: false,
        deleted_by: userId,
        // Free the unique phone number so a new driver can reuse it.
        // The record is kept (soft delete) so any trips that referenced it stay valid.
        phone_primary: null
      }
    });
    res.json({ success: true, data: { message: 'Driver deleted successfully' } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to delete driver' } });
  }
};


export const bulkDeleteDrivers = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'No IDs provided' } });
    }

    await prisma.driver.updateMany({
      where: { id: { in: ids } },
      data: {
        deletedAt: new Date(),
        isActive: false,
        deleted_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully deleted ${ids.length} drivers` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk delete drivers` } });
  }
};

export const bulkUpdateDriverStatus = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids, status } = req.body;

    if (!Array.isArray(ids) || ids.length === 0 || !status) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'IDs and status are required' } });
    }

    await prisma.driver.updateMany({
      where: { id: { in: ids } },
      data: {
        status: status as DriverStatus,
        updated_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully updated ${ids.length} drivers` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk update drivers` } });
  }
};
