import { Request, Response } from 'express';
import { prisma } from '../index';
import { TripStatus } from '@prisma/client';

/**
 * The vehicle assigned to the driver's current active trip (drivers have no
 * standing vehicle assignment). Returns null when there's no active trip.
 */
export const getAssignedVehicle = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });

  try {
    const activeTrip = await prisma.trip.findFirst({
      where: {
        driverId,
        deletedAt: null,
        status: { in: [TripStatus.Dispatched, TripStatus.AtPickup, TripStatus.InTransit, TripStatus.AtDelivery] },
      },
      orderBy: { createdAt: 'desc' },
      select: {
        ref_id: true,
        vehicle: {
          select: {
            id: true,
            ref_id: true,
            plate_number: true,
            asset_type: true,
            status: true,
            capacity_kg: true,
            current_odometer: true,
            trailer_number: true,
            trailer_type: true,
          },
        },
      },
    });

    res.json({
      success: true,
      data: activeTrip?.vehicle ? { ...activeTrip.vehicle, trip_ref_id: activeTrip.ref_id } : null,
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};
