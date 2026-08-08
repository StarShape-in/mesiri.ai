import { Request, Response } from 'express';
import { prisma } from '../index';
import { TripStatus, DocType } from '@prisma/client';
import { isValidTransition, completeTripAndInvoice, stampStopTransition, type DelayDetection } from '../services/tripLifecycle';
import { notifyOperatorsOfDelay } from './notificationController';

export const getCurrentTrip = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });

  const include = {
    customer: true,
    vehicle: true,
    stops: { orderBy: { stop_sequence: 'asc' as const } },
  };

  try {
    // Prefer an in-progress / dispatched trip.
    let trip = await prisma.trip.findFirst({
      where: {
        driverId,
        deletedAt: null,
        status: {
          in: [TripStatus.Dispatched, TripStatus.AtPickup, TripStatus.InTransit, TripStatus.AtDelivery]
        }
      },
      include,
      orderBy: { updatedAt: 'desc' },
    });

    // Otherwise show the next upcoming trip that's assigned but not yet dispatched
    // (created for this driver in the operator panel).
    if (!trip) {
      trip = await prisma.trip.findFirst({
        where: { driverId, deletedAt: null, status: TripStatus.Draft },
        include,
        orderBy: [{ planned_start: 'asc' }, { createdAt: 'asc' }],
      });
    }

    res.json({ success: true, data: trip ?? null });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

/**
 * Past trips for the logged-in driver: finished, invoiced, or cancelled,
 * newest first. Supports ?limit (default 30, max 100).
 */
export const getTripHistory = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });

  const parsedLimit = parseInt(String(req.query.limit ?? ''), 10);
  const limit = Number.isFinite(parsedLimit) ? Math.min(Math.max(parsedLimit, 1), 100) : 30;

  try {
    const trips = await prisma.trip.findMany({
      where: {
        driverId,
        deletedAt: null,
        status: { in: [TripStatus.Completed, TripStatus.Invoiced, TripStatus.Cancelled] },
      },
      include: {
        customer: true,
        vehicle: true,
        stops: { orderBy: { stop_sequence: 'asc' } },
      },
      orderBy: [{ actual_end: 'desc' }, { createdAt: 'desc' }],
      take: limit,
    });

    res.json({ success: true, data: trips });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

export const updateTripStatus = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  const id = req.params.id as string;
  const { status } = req.body;

  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });
  
  if (!Object.values(TripStatus).includes(status)) {
    return res.status(400).json({ success: false, error: { message: 'Invalid status' } });
  }

  try {
    const trip = await prisma.trip.findFirst({
      where: { id, driverId, deletedAt: null }
    });

    if (!trip) {
      return res.status(404).json({ success: false, error: { message: 'Trip not found or not assigned to you' } });
    }
    if (!isValidTransition(trip.status, status)) {
      return res.status(400).json({ success: false, error: { message: 'That status change is not allowed from the trip\'s current state' } });
    }

    // Completing a trip always goes through the shared helper — this is the
    // path that previously let a driver mark a trip Completed without ever
    // generating its invoice, since only the web dashboard's deliveryVerify
    // did that.
    if (status === TripStatus.Completed) {
      // Pass null, not driverId: updated_by/created_by are User.id columns
      // elsewhere in the schema — a driver-authenticated request has no
      // User.id, and writing Driver.id there would silently mix ID spaces.
      const updatedTrip = await prisma.$transaction((tx) => completeTripAndInvoice(tx, id, null));
      const full = await prisma.trip.findUnique({
        where: { id: updatedTrip.id },
        include: { customer: true, vehicle: true, stops: true },
      });
      return res.json({ success: true, data: full });
    }

    // This is the path the driver's app actually takes — including the GPS
    // geofence auto-arrival. It previously moved the trip's status without
    // recording anything on the stop, so a driver arriving through the app
    // left no arrival time at all and the trip was invisible to the delay
    // report. Wrapped in a transaction so status and clock cannot diverge.
    let delay: DelayDetection | null = null;
    const updatedTrip = await prisma.$transaction(async (tx) => {
      // Stamped before the trip is re-read, so the stops in the response
      // already carry the new timestamp — the app renders its timeline
      // straight off this payload.
      delay = await stampStopTransition(tx, id, status as TripStatus);
      return tx.trip.update({
        where: { id },
        data: {
          status,
          actual_start: status === TripStatus.InTransit && !trip.actual_start ? new Date() : undefined,
        },
        include: { customer: true, vehicle: true, stops: true }
      });
    });

    // This is the path the GPS geofence takes, so it is where most real
    // delays surface. Fired post-commit, and never allowed to fail the
    // driver's status update.
    if (delay) await notifyOperatorsOfDelay(delay);

    res.json({ success: true, data: updatedTrip });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

/**
 * Upload a trip photo (cargo at pickup, or POD at delivery) and attach it to the
 * trip as a Document. Expects multipart form-data: file field "file" + "kind".
 */
export const uploadTripPhoto = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  const id = req.params.id as string;
  const kind = req.body?.kind === 'pod' ? 'pod' : 'cargo';

  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });
  if (!req.file) return res.status(400).json({ success: false, error: { message: 'No photo uploaded' } });

  try {
    const trip = await prisma.trip.findFirst({ where: { id, driverId, deletedAt: null } });
    if (!trip) return res.status(404).json({ success: false, error: { message: 'Trip not found or not assigned to you' } });

    const document = await prisma.document.create({
      data: {
        entity_type: 'Trip',
        entity_id: id,
        // No dedicated "cargo photo" enum value; POD for delivery, Waybill for pickup cargo.
        doc_type: kind === 'pod' ? DocType.POD : DocType.Waybill,
        file_url: `/uploads/${req.file.filename}`,
        mime_type: req.file.mimetype,
      },
    });

    res.status(201).json({ success: true, data: document });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};
