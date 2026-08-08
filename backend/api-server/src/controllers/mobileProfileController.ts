import { Request, Response } from 'express';
import { prisma } from '../index';
import { TripStatus } from '@prisma/client';

/**
 * The logged-in driver's profile: identity, license, contact, and the vehicle
 * from their current active trip (drivers have no standing vehicle assignment).
 */
export const getProfile = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });

  try {
    const driver = await prisma.driver.findUnique({
      where: { id: driverId },
      select: {
        id: true,
        ref_id: true,
        first_name: true,
        last_name: true,
        phone_primary: true,
        status: true,
        license_number: true,
        license_expiry: true,
        createdAt: true,
      },
    });

    if (!driver) return res.status(404).json({ success: false, error: { message: 'Driver not found' } });

    const activeTrip = await prisma.trip.findFirst({
      where: {
        driverId,
        deletedAt: null,
        status: { in: [TripStatus.Dispatched, TripStatus.AtPickup, TripStatus.InTransit, TripStatus.AtDelivery] },
      },
      select: { vehicle: { select: { id: true, plate_number: true, asset_type: true } } },
      orderBy: { createdAt: 'desc' },
    });

    res.json({
      success: true,
      data: {
        ...driver,
        name: `${driver.first_name} ${driver.last_name}`,
        current_vehicle: activeTrip?.vehicle ?? null,
      },
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};
