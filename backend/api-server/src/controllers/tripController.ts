import { Request, Response } from 'express';
import { prisma } from '../index';
import { generateRefId } from '../utils/refId';
import { createDriverNotification, notifyOperatorsOfDelay } from './notificationController';
import { Prisma, TripStatus, StopType, PaymentStatus, DriverStatus, AssetStatus } from '@prisma/client';
import { logger } from '../utils/logger';
import { isValidTransition, completeTripAndInvoice, stampStopTransition, type DelayDetection } from '../services/tripLifecycle';

const isUuid = (val: any): boolean =>
  typeof val === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(val);

/**
 * Notify a driver they've been assigned a trip. Notifications target the driver
 * directly (Notification.driverId). Call after the assignment transaction commits.
 */
async function notifyDriverAssigned(
  driverId: string,
  trip: { id: string; ref_id: string | null },
) {
  try {
    await createDriverNotification(
      driverId,
      'Trip Assignment',
      `You've been assigned trip ${trip.ref_id ?? ''}. Open the app to start.`.replace('  ', ' '),
      'Trip',
      'Trip',
      trip.id,
    );
  } catch (err) {
    logger.error({ err }, 'Failed to send driver assignment notification');
  }
}

export const getTrips = async (req: Request, res: Response) => {
  try {
    const { status, driver_id, customer_id, search, date_filter, start_date, end_date, page = '1', per_page = '20' } = req.query;

    const pageNumber = parseInt(page as string);
    const limit = parseInt(per_page as string);
    const skip = (pageNumber - 1) * limit;

    const whereClause: Prisma.TripWhereInput = { deletedAt: null };
    if (status) whereClause.status = status as TripStatus;
    if (driver_id) whereClause.driverId = driver_id as string;
    if (customer_id) whereClause.customerId = customer_id as string;
    if (search) {
      whereClause.OR = [
        { ref_id: { contains: search as string, mode: 'insensitive' } },
        { cargo_type: { contains: search as string, mode: 'insensitive' } },
        { customer: { name: { contains: search as string, mode: 'insensitive' } } },
      ];
    }

    let startDateObj: Date | undefined;
    let endDateObj: Date | undefined;
    const now = new Date();

    if (date_filter === 'Today') {
      startDateObj = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
      endDateObj = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
    } else if (date_filter === 'ThisWeek') {
      const day = now.getDay();
      const diffToSun = now.getDate() - day;
      startDateObj = new Date(now.getFullYear(), now.getMonth(), diffToSun, 0, 0, 0, 0);
      endDateObj = new Date(now.getFullYear(), now.getMonth(), diffToSun + 6, 23, 59, 59, 999);
    } else if (date_filter === 'ThisMonth') {
      startDateObj = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0);
      endDateObj = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59, 999);
    } else {
      if (start_date) startDateObj = new Date(start_date as string);
      if (end_date) endDateObj = new Date(end_date as string);
    }

    if (startDateObj || endDateObj) {
      const dateConditions: Prisma.TripWhereInput[] = [];
      if (startDateObj) {
        dateConditions.push({
          OR: [
            { planned_start: { gte: startDateObj } },
            { AND: [{ planned_start: null }, { createdAt: { gte: startDateObj } }] }
          ]
        });
      }
      if (endDateObj) {
        dateConditions.push({
          OR: [
            { planned_start: { lte: endDateObj } },
            { AND: [{ planned_start: null }, { createdAt: { lte: endDateObj } }] }
          ]
        });
      }
      if (dateConditions.length > 0) {
        whereClause.AND = dateConditions;
      }
    }

    const [trips, total] = await Promise.all([
      prisma.trip.findMany({
        where: whereClause,
        skip,
        take: limit,
        orderBy: [{ status: 'asc' }, { createdAt: 'desc' }],
        include: { driver: true, vehicle: true, customer: true }
      }),
      prisma.trip.count({ where: whereClause })
    ]);

    res.json({
      success: true,
      data: trips,
      meta: {
        page: pageNumber,
        per_page: limit,
        total,
        total_pages: Math.ceil(total / limit)
      }
    });
  } catch (error) {
    logger.error({ err: error }, 'Failed to fetch trips');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch trips' } });
  }
};

export const getTripById = async (req: Request, res: Response) => {
  try {
    const trip = await prisma.trip.findUnique({
      where: { id: req.params.id as string, deletedAt: null },
      include: { driver: true, vehicle: true, customer: true, invoices: true, stops: { orderBy: { stop_sequence: 'asc' } } }
    });

    if (!trip) {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Trip not found' } });
    }

    res.json({ success: true, data: trip });
  } catch (error) {
    logger.error({ err: error }, 'Failed to fetch trip by id');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch trip' } });
  }
};

export const createTrip = async (req: Request, res: Response) => {
  try {
    const { customer_id, driver_id, vehicle_id, cargo_type, planned_start, stops } = req.body;

    const createdBy = isUuid((req as any).user?.id) ? (req as any).user.id : null;
    const parsedPlannedStart = (planned_start && !isNaN(Date.parse(planned_start)))
      ? new Date(planned_start)
      : null;

    let trip;
    let attempts = 0;
    const maxAttempts = 3;

    while (attempts < maxAttempts) {
      attempts++;
      try {
        const ref_id = await generateRefId('TRP', () =>
          prisma.trip.findMany({ select: { ref_id: true } }));

        trip = await prisma.$transaction(async (tx) => {
          const customer = await tx.customer.findFirst({ where: { id: customer_id, deletedAt: null } });
          if (!customer) {
            throw new Error('CUSTOMER_NOT_FOUND');
          }

          // Driver and vehicle are optional — dispatchers can create the trip
          // now and assign either later via dispatchTrip.
          if (driver_id) {
            const driver = await tx.driver.findFirst({ where: { id: driver_id, deletedAt: null } });
            if (!driver) {
              throw new Error('DRIVER_NOT_FOUND');
            }

            // Atomically claim the driver: the UPDATE only matches (and
            // locks) the row if it's still Available, so two concurrent
            // requests racing for the same driver can't both win — the
            // loser's WHERE clause re-evaluates against the winner's
            // committed status and matches zero rows.
            const driverClaim = await tx.driver.updateMany({
              where: { id: driver_id, status: 'Available' },
              data: { status: 'OnTrip' },
            });
            if (driverClaim.count === 0) {
              throw new Error('DRIVER_UNAVAILABLE');
            }
          }

          if (vehicle_id) {
            const vehicle = await tx.vehicle.findFirst({ where: { id: vehicle_id, deletedAt: null } });
            if (!vehicle) {
              throw new Error('VEHICLE_NOT_FOUND');
            }

            const vehicleClaim = await tx.vehicle.updateMany({
              where: { id: vehicle_id, status: 'Available' },
              data: { status: 'OnTrip' },
            });
            if (vehicleClaim.count === 0) {
              throw new Error('VEHICLE_UNAVAILABLE');
            }
          }

          return tx.trip.create({
            data: {
              ref_id,
              customerId: customer_id,
              ...(driver_id ? { driverId: driver_id } : {}),
              ...(vehicle_id ? { vehicleId: vehicle_id } : {}),
              cargo_type: cargo_type || 'General Goods',
              planned_start: parsedPlannedStart,
              status: (driver_id && vehicle_id) ? TripStatus.Dispatched : TripStatus.Draft,
              ...(createdBy ? { created_by: createdBy } : {}),
              stops: {
                create: (stops || []).map((stop: any, index: number) => ({
                  stop_sequence: index + 1,
                  stop_type: stop.stop_type as StopType,
                  location_lat: parseFloat(stop.lat),
                  location_lng: parseFloat(stop.lng),
                  // Empty string collapses to null so "unnamed" is one value in
                  // reports, not two that group separately.
                  location_name: String(stop.location_name ?? '').trim() || null,
                  planned_arrival: (stop.planned_arrival && !isNaN(Date.parse(stop.planned_arrival)))
                    ? new Date(stop.planned_arrival)
                    : null
                }))
              }
            },
            include: { stops: true }
          });
        });

        break;
      } catch (err: any) {
        if (err.code === 'P2002' && attempts < maxAttempts) {
          logger.warn({ err }, `Unique constraint collision on ref_id. Retrying attempt ${attempts + 1}...`);
          continue;
        }
        throw err;
      }
    }

    if (!trip) {
      throw new Error('FAILED_TO_CREATE_TRIP');
    }

    // Notify driver asynchronously without throwing
    if (driver_id) await notifyDriverAssigned(driver_id, trip);

    res.status(201).json({ success: true, data: trip });
  } catch (error: any) {
    logger.error({ err: error, body: req.body }, 'Failed to create trip');
    if (
      error.message === 'CUSTOMER_NOT_FOUND' ||
      error.message === 'DRIVER_NOT_FOUND' ||
      error.message === 'VEHICLE_NOT_FOUND' ||
      error.message === 'DRIVER_UNAVAILABLE' ||
      error.message === 'VEHICLE_UNAVAILABLE'
    ) {
      return res.status(400).json({ success: false, error: { code: 'CONFLICT', message: error.message } });
    }
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: error.message || 'Failed to create trip' } });
  }
};

export const updateTripStatus = async (req: Request, res: Response) => {
  try {
    const { status } = req.body;
    const tripId = req.params.id as string;

    if (!Object.values(TripStatus).includes(status)) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'Invalid status' } });
    }

    let delay: DelayDetection | null = null;

    const trip = await prisma.$transaction(async (tx) => {
      const current = await tx.trip.findUnique({ where: { id: tripId } });
      if (!current) throw new Error('NOT_FOUND');
      if (!isValidTransition(current.status, status)) throw new Error('INVALID_TRANSITION');
      // Draft trips can be created with "assign later" — don't let a status
      // update dispatch a trip that still has no driver/vehicle (that must
      // go through dispatchTrip, which claims them).
      if (status === TripStatus.Dispatched && (!current.driverId || !current.vehicleId)) {
        throw new Error('MISSING_ASSIGNMENT');
      }

      // Completing a trip always goes through the shared helper so every
      // path that can complete a trip also generates its invoice.
      if (status === TripStatus.Completed) {
        return completeTripAndInvoice(tx, tripId, (req as any).user?.id);
      }

      const updateData: any = { status: status as TripStatus, updated_by: (req as any).user?.id };
      if (status === 'InTransit') updateData.actual_start = new Date();

      const updated = await tx.trip.update({ where: { id: tripId }, data: updateData });

      delay = await stampStopTransition(tx, tripId, status as TripStatus);

      // Leaving the trip permanently via Cancelled must release the
      // driver/vehicle back to Available — otherwise they stay stuck on
      // "OnTrip" with no trip left to free them.
      if (status === TripStatus.Cancelled) {
        if (updated.driverId) {
          await tx.driver.update({ where: { id: updated.driverId }, data: { status: DriverStatus.Available } });
        }
        if (updated.vehicleId) {
          await tx.vehicle.update({ where: { id: updated.vehicleId }, data: { status: AssetStatus.Available } });
        }
      }

      return updated;
    });

    // Alerted only once the transaction has committed, so operators are never
    // told about a delay on a trip update that then rolled back.
    if (delay) await notifyOperatorsOfDelay(delay);

    res.json({ success: true, data: trip });
  } catch (error: any) {
    if (error.message === 'NOT_FOUND') {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Trip not found' } });
    }
    if (error.message === 'INVALID_TRANSITION') {
      return res.status(400).json({ success: false, error: { code: 'INVALID_TRANSITION', message: 'That status change is not allowed from the trip\'s current state' } });
    }
    if (error.message === 'MISSING_ASSIGNMENT') {
      return res.status(400).json({ success: false, error: { code: 'MISSING_ASSIGNMENT', message: 'Assign a driver and vehicle before dispatching this trip' } });
    }
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to update trip status' } });
  }
};

// Driver Cash Payment Workflow endpoint
export const approveDriverPayment = async (req: Request, res: Response) => {
  try {
    const { amount, reason } = req.body;

    if (!amount || !reason) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'Amount and reason required' } });
    }

    const trip = await prisma.trip.update({
      where: { id: req.params.id as string },
      data: {
        extra_driver_payment: parseFloat(amount),
        payment_reason: reason,
        payment_status: PaymentStatus.Approved,
        payment_approved_by: (req as any).user?.id,
        payment_date: new Date(),
        updated_by: (req as any).user?.id
      }
    });

    res.json({ success: true, data: trip });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to approve payment' } });
  }
};

// ==========================================
// PHASE 1: DISPATCH & ASSIGNMENT
// ==========================================

export const dispatchTrip = async (req: Request, res: Response) => {
  try {
    const { driver_id, vehicle_id } = req.body;
    const tripId = req.params.id as string;

    if (!driver_id && !vehicle_id) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'driver_id or vehicle_id required' } });
    }

    // Run in a transaction to ensure atomic state updates. driver_id/vehicle_id
    // are independently optional — a trip created with "assign later" can have
    // just one filled in here, and the other assigned in a later call.
    const result = await prisma.$transaction(async (tx) => {
      const trip = await tx.trip.findFirst({ where: { id: tripId, deletedAt: null } });
      if (!trip) {
        throw new Error('NOT_FOUND');
      }

      // Atomically claim the driver/vehicle — see createTrip for why this
      // must be a conditional UPDATE rather than SELECT-then-UPDATE.
      if (driver_id) {
        const driverClaim = await tx.driver.updateMany({
          where: { id: driver_id, status: 'Available' },
          data: { status: 'OnTrip' },
        });
        if (driverClaim.count === 0) {
          throw new Error('DRIVER_UNAVAILABLE');
        }
      }

      if (vehicle_id) {
        const vehicleClaim = await tx.vehicle.updateMany({
          where: { id: vehicle_id, status: 'Available' },
          data: { status: 'OnTrip' },
        });
        if (vehicleClaim.count === 0) {
          throw new Error('VEHICLE_UNAVAILABLE');
        }
      }

      const finalDriverId = driver_id || trip.driverId;
      const finalVehicleId = vehicle_id || trip.vehicleId;

      const updatedTrip = await tx.trip.update({
        where: { id: tripId },
        data: {
          ...(driver_id ? { driverId: driver_id } : {}),
          ...(vehicle_id ? { vehicleId: vehicle_id } : {}),
          // Only moves out of Draft once both a driver and a vehicle are on
          // the trip — a single-sided assignment leaves it in Draft.
          ...(finalDriverId && finalVehicleId ? { status: 'Dispatched' as const } : {}),
          updated_by: (req as any).user?.id
        }
      });

      return updatedTrip;
    });

    // Notify the driver after the dispatch commits.
    if (driver_id) await notifyDriverAssigned(driver_id, result);

    res.json({ success: true, data: result });
  } catch (error: any) {
    if (error.message === 'NOT_FOUND') {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Trip not found' } });
    }
    if (error.message === 'DRIVER_UNAVAILABLE' || error.message === 'VEHICLE_UNAVAILABLE') {
      return res.status(400).json({ success: false, error: { code: 'CONFLICT', message: error.message } });
    }
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to dispatch trip' } });
  }
};

export const replaceDriver = async (req: Request, res: Response) => {
  try {
    const { new_driver_id } = req.body;
    const tripId = req.params.id as string;

    if (!new_driver_id) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'new_driver_id required' } });
    }

    const result = await prisma.$transaction(async (tx) => {
      const trip = await tx.trip.findUnique({ where: { id: tripId } });
      if (!trip || !trip.driverId) throw new Error('TRIP_OR_DRIVER_NOT_FOUND');

      // Atomically claim the new driver — see createTrip for why this must be
      // a conditional UPDATE rather than SELECT-then-UPDATE.
      const claim = await tx.driver.updateMany({
        where: { id: new_driver_id, status: 'Available' },
        data: { status: 'OnTrip' },
      });
      if (claim.count === 0) throw new Error('NEW_DRIVER_UNAVAILABLE');

      // Free old driver
      await tx.driver.update({ where: { id: trip.driverId }, data: { status: 'Available' } });

      const updatedTrip = await tx.trip.update({
        where: { id: tripId },
        data: {
          driverId: new_driver_id,
          updated_by: (req as any).user?.id
        }
      });

      return updatedTrip;
    });

    // Notify the newly-assigned driver after the swap commits.
    await notifyDriverAssigned(new_driver_id, result);

    res.json({ success: true, data: result });
  } catch (error: any) {
    if (['TRIP_OR_DRIVER_NOT_FOUND', 'NEW_DRIVER_UNAVAILABLE'].includes(error.message)) {
      return res.status(400).json({ success: false, error: { code: 'CONFLICT', message: error.message } });
    }
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to replace driver' } });
  }
};

// ==========================================
// PHASE 2: DRIVER WORKFLOW
// ==========================================

export const pickupArrive = async (req: Request, res: Response) => {
  try {
    const tripId = req.params.id as string;

    const trip = await prisma.trip.findUnique({ where: { id: tripId } });
    if (!trip) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Trip not found' } });
    if (!isValidTransition(trip.status, TripStatus.AtPickup)) {
      return res.status(400).json({ success: false, error: { code: 'INVALID_TRANSITION', message: 'That status change is not allowed from the trip\'s current state' } });
    }

    // Stop clock and trip status move together: a committed arrival time on a
    // trip that never reached AtPickup (or the reverse) is exactly the kind of
    // split the delay report cannot interpret afterwards.
    let delay: DelayDetection | null = null;
    const updatedTrip = await prisma.$transaction(async (tx) => {
      const updated = await tx.trip.update({
        where: { id: tripId },
        data: { status: 'AtPickup', updated_by: (req as any).user?.id }
      });
      delay = await stampStopTransition(tx, tripId, TripStatus.AtPickup);
      return updated;
    });

    if (delay) await notifyOperatorsOfDelay(delay);

    res.json({ success: true, data: updatedTrip });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to record pickup arrival' } });
  }
};

export const pickupVerify = async (req: Request, res: Response) => {
  try {
    const tripId = req.params.id as string;

    const trip = await prisma.trip.findUnique({ where: { id: tripId } });
    if (!trip) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Trip not found' } });
    if (!isValidTransition(trip.status, TripStatus.InTransit)) {
      return res.status(400).json({ success: false, error: { code: 'INVALID_TRANSITION', message: 'That status change is not allowed from the trip\'s current state' } });
    }

    const updatedTrip = await prisma.$transaction(async (tx) => {
      const updated = await tx.trip.update({
        where: { id: tripId },
        data: {
          status: 'InTransit',
          actual_start: new Date(),
          updated_by: (req as any).user?.id
        }
      });
      // Leaving pickup closes the loading window that started at AtPickup.
      await stampStopTransition(tx, tripId, TripStatus.InTransit);
      return updated;
    });

    res.json({ success: true, data: updatedTrip });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to verify pickup' } });
  }
};

export const deliveryVerify = async (req: Request, res: Response) => {
  try {
    const tripId = req.params.id as string;

    const result = await prisma.$transaction(async (tx) => {
      const current = await tx.trip.findUnique({ where: { id: tripId } });
      if (!current) throw new Error('NOT_FOUND');
      if (!isValidTransition(current.status, TripStatus.Completed)) throw new Error('INVALID_TRANSITION');

      return completeTripAndInvoice(tx, tripId, (req as any).user?.id);
    });

    res.json({ success: true, data: result });
  } catch (error: any) {
    if (error.message === 'NOT_FOUND') {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Trip not found' } });
    }
    if (error.message === 'INVALID_TRANSITION') {
      return res.status(400).json({ success: false, error: { code: 'INVALID_TRANSITION', message: 'That status change is not allowed from the trip\'s current state' } });
    }
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to verify delivery' } });
  }
};

/**
 * Record why a stop was reached late. Operator-only by design: drivers already
 * report the cause in the WhatsApp group, and the office is better placed to
 * classify it than a driver working a phone in a cab.
 *
 * Re-logging is allowed — a first guess ("Traffic") often turns out to be
 * something else once the driver is actually reached, and a wrong reason left
 * frozen in place would quietly skew the report it feeds.
 */
export const logStopDelay = async (req: Request, res: Response) => {
  try {
    const { id: tripId, stopId } = req.params as { id: string; stopId: string };
    const { delay_reason, delay_note } = req.body;

    const stop = await prisma.tripStop.findFirst({
      where: { id: stopId, tripId, deletedAt: null },
    });
    if (!stop) {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Stop not found on this trip' } });
    }
    // Nothing to explain about a stop the driver has not reached yet, and
    // allowing it would put reasons on trips that are still running fine.
    if (!stop.actual_arrival) {
      return res.status(400).json({ success: false, error: { code: 'NOT_ARRIVED', message: 'This stop has no recorded arrival yet' } });
    }

    const updated = await prisma.tripStop.update({
      where: { id: stopId },
      data: {
        delay_reason,
        delay_note: String(delay_note ?? '').trim() || null,
        delay_logged_by: (req as any).user?.id ?? null,
        delay_logged_at: new Date(),
      },
    });

    res.json({ success: true, data: updated });
  } catch (error) {
    logger.error({ err: error }, 'Failed to log stop delay reason');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to log delay reason' } });
  }
};


/** Trip statuses where the assigned driver/vehicle are actively held as `OnTrip`. */
const IN_FLIGHT_STATUSES: TripStatus[] = [
  TripStatus.Dispatched, TripStatus.AtPickup, TripStatus.InTransit, TripStatus.AtDelivery,
];

export const bulkDeleteTrips = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'No IDs provided' } });
    }

    await prisma.$transaction(async (tx) => {
      // Deleting an in-flight trip must release its driver/vehicle back to
      // Available — otherwise they stay stuck on "OnTrip" forever with no
      // trip left to complete them (this was a real bug: deleted trip, driver
      // still showed on duty).
      const trips = await tx.trip.findMany({
        where: { id: { in: ids }, deletedAt: null, status: { in: IN_FLIGHT_STATUSES } },
        select: { driverId: true, vehicleId: true },
      });

      await tx.trip.updateMany({
        where: { id: { in: ids } },
        data: {
          deletedAt: new Date(),
          isActive: false,
          deleted_by: userId
        }
      });

      const driverIds = [...new Set(trips.map((t) => t.driverId).filter((id): id is string => !!id))];
      const vehicleIds = [...new Set(trips.map((t) => t.vehicleId).filter((id): id is string => !!id))];

      if (driverIds.length) {
        await tx.driver.updateMany({ where: { id: { in: driverIds } }, data: { status: DriverStatus.Available } });
      }
      if (vehicleIds.length) {
        await tx.vehicle.updateMany({ where: { id: { in: vehicleIds } }, data: { status: AssetStatus.Available } });
      }
    });

    res.json({ success: true, data: { message: `Successfully deleted ${ids.length} trips` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk delete trips` } });
  }
};

export const bulkUpdateTripStatus = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids, status } = req.body;

    if (!Array.isArray(ids) || ids.length === 0 || !status) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'IDs and status are required' } });
    }
    if (!Object.values(TripStatus).includes(status)) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'Invalid status' } });
    }

    const { updated, skipped } = await prisma.$transaction(async (tx) => {
      const trips = await tx.trip.findMany({
        where: { id: { in: ids }, deletedAt: null },
        select: { id: true, status: true, driverId: true, vehicleId: true },
      });

      const validIds = trips.filter((t) => isValidTransition(t.status, status)).map((t) => t.id);
      const skippedCount = trips.length - validIds.length;

      if (validIds.length === 0) return { updated: 0, skipped: skippedCount };

      // Completing a trip always goes through the shared helper so bulk
      // completion also generates invoices, same as the single-trip path.
      if (status === TripStatus.Completed) {
        for (const id of validIds) {
          await completeTripAndInvoice(tx, id, userId);
        }
        return { updated: validIds.length, skipped: skippedCount };
      }

      await tx.trip.updateMany({
        where: { id: { in: validIds } },
        data: { status: status as TripStatus, updated_by: userId },
      });

      // Same release rule as the single-trip update: Cancelled frees the
      // driver/vehicle back to Available.
      if (status === TripStatus.Cancelled) {
        const affected = trips.filter((t) => validIds.includes(t.id));
        const driverIds = [...new Set(affected.map((t) => t.driverId).filter((id): id is string => !!id))];
        const vehicleIds = [...new Set(affected.map((t) => t.vehicleId).filter((id): id is string => !!id))];
        if (driverIds.length) {
          await tx.driver.updateMany({ where: { id: { in: driverIds } }, data: { status: DriverStatus.Available } });
        }
        if (vehicleIds.length) {
          await tx.vehicle.updateMany({ where: { id: { in: vehicleIds } }, data: { status: AssetStatus.Available } });
        }
      }

      return { updated: validIds.length, skipped: skippedCount };
    });

    res.json({
      success: true,
      data: {
        message: skipped > 0
          ? `Updated ${updated} trip(s); skipped ${skipped} with an invalid status transition`
          : `Successfully updated ${updated} trips`,
      },
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk update trips` } });
  }
};

/**
 * Get all completed trips pending post-trip financial settlement / waiting-labor check
 */
export const getUnsettledCompletedTrips = async (req: Request, res: Response) => {
  try {
    const trips = await prisma.trip.findMany({
      where: {
        deletedAt: null,
        status: { in: [TripStatus.Completed, TripStatus.Invoiced] },
        is_post_trip_settled: false,
      },
      include: {
        customer: true,
        driver: true,
        vehicle: true,
      },
      orderBy: { createdAt: 'desc' },
    });

    res.json({
      success: true,
      data: trips,
      count: trips.length,
    });
  } catch (error) {
    logger.error({ err: error }, 'Failed to fetch unsettled completed trips');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch unsettled trips' } });
  }
};

/**
 * Update post-trip financial fields (Waiting/Labor, Additional Stops, Trip Charges, Carrier)
 * and automatically update linked Invoice total.
 */
export const updateTripFinancials = async (req: Request, res: Response) => {
  try {
    const tripId = req.params.id as string;
    const {
      waiting_labor_charges,
      additional_stop_charges,
      trip_charges,
      billing_amount,
      carrier_name,
      is_post_trip_settled = true,
    } = req.body;

    const result = await prisma.$transaction(async (tx) => {
      const trip = await tx.trip.findUnique({
        where: { id: tripId, deletedAt: null },
      });

      if (!trip) throw new Error('NOT_FOUND');

      const updatedTrip = await tx.trip.update({
        where: { id: tripId },
        data: {
          waiting_labor_charges: waiting_labor_charges !== undefined ? parseFloat(waiting_labor_charges) : trip.waiting_labor_charges,
          additional_stop_charges: additional_stop_charges !== undefined ? parseFloat(additional_stop_charges) : trip.additional_stop_charges,
          trip_charges: trip_charges !== undefined ? parseFloat(trip_charges) : trip.trip_charges,
          billing_amount: billing_amount !== undefined ? parseFloat(billing_amount) : trip.billing_amount,
          carrier_name: carrier_name !== undefined ? carrier_name : trip.carrier_name,
          is_post_trip_settled: Boolean(is_post_trip_settled),
          updated_by: (req as any).user?.id,
        },
        include: { customer: true, driver: true, vehicle: true, invoices: true },
      });

      // Recalculate invoice total if an invoice exists for this trip
      const existingInvoice = await tx.invoice.findFirst({ where: { tripId: trip.id } });
      if (existingInvoice) {
        const baseBilling = updatedTrip.billing_amount ?? existingInvoice.subtotal;
        const newTotal = baseBilling + updatedTrip.waiting_labor_charges + updatedTrip.additional_stop_charges;

        await tx.invoice.update({
          where: { id: existingInvoice.id },
          data: {
            subtotal: baseBilling,
            total_amount: newTotal,
            updated_by: (req as any).user?.id,
          },
        });
      }

      return updatedTrip;
    });

    res.json({ success: true, data: result });
  } catch (error: any) {
    if (error.message === 'NOT_FOUND') {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Trip not found' } });
    }
    logger.error({ err: error }, 'Failed to update trip financials');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to update trip financials' } });
  }
};

