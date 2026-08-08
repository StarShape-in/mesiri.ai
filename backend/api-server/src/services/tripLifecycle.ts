import { Prisma, TripStatus, DriverStatus, AssetStatus, StopType } from '@prisma/client';
import { generateRefId } from '../utils/refId';

/**
 * Legal next statuses for a trip, keyed by current status. Enforced by every
 * status-changing endpoint (web + mobile) so a trip can't skip stages (e.g.
 * straight to Invoiced without ever being Completed) or go backwards out of a
 * terminal state.
 */
export const ALLOWED_TRANSITIONS: Record<TripStatus, TripStatus[]> = {
  [TripStatus.Draft]: [TripStatus.Dispatched, TripStatus.Cancelled],
  [TripStatus.Dispatched]: [TripStatus.AtPickup, TripStatus.Cancelled],
  [TripStatus.AtPickup]: [TripStatus.InTransit, TripStatus.Cancelled],
  [TripStatus.InTransit]: [TripStatus.AtDelivery, TripStatus.Cancelled],
  [TripStatus.AtDelivery]: [TripStatus.Completed, TripStatus.Cancelled],
  [TripStatus.Completed]: [TripStatus.Invoiced],
  [TripStatus.Invoiced]: [],
  [TripStatus.Cancelled]: [],
};

export function isValidTransition(from: TripStatus, to: TripStatus): boolean {
  if (from === to) return true; // no-op update, not a transition
  return ALLOWED_TRANSITIONS[from]?.includes(to) ?? false;
}

/**
 * The moment each transition represents at a stop. Four timestamps across a
 * trip, and every delay figure the reports produce is derived from them:
 *
 *   -> AtPickup     pickup arrived     was the driver late to collect
 *   -> InTransit    pickup departed    how long loading held them
 *   -> AtDelivery   dropoff arrived    the number the customer judges us on
 *   -> Completed    dropoff departed   how long unloading held them
 */
const STOP_MARK_BY_STATUS: Partial<
  Record<TripStatus, { stop_type: StopType; field: 'actual_arrival' | 'actual_departure' }>
> = {
  [TripStatus.AtPickup]: { stop_type: StopType.Pickup, field: 'actual_arrival' },
  [TripStatus.InTransit]: { stop_type: StopType.Pickup, field: 'actual_departure' },
  [TripStatus.AtDelivery]: { stop_type: StopType.Dropoff, field: 'actual_arrival' },
  [TripStatus.Completed]: { stop_type: StopType.Dropoff, field: 'actual_departure' },
};

/**
 * How late an arrival must be before it counts as a delay worth explaining.
 * Below this it is ordinary variance, and flagging it would only train
 * operators to ignore the alert.
 */
export const DELAY_THRESHOLD_MINUTES = 30;

/** A late arrival nobody has explained yet. */
export interface DelayDetection {
  tripId: string;
  tripRefId: string | null;
  stopId: string;
  stopType: StopType;
  locationName: string | null;
  delayMinutes: number;
}

/**
 * Record the real-world moment a status change stands for, and report back
 * whether that moment was late.
 *
 * **Every path that changes a trip's status must call this.** A stop that is
 * missed here is missed permanently — the moment has passed and no later job
 * can reconstruct when the driver actually arrived. That is exactly how
 * dropoff arrival came to be backfilled at completion time (making every
 * delivery look like it arrived the instant it finished), and how the mobile
 * geofence path recorded nothing at all.
 *
 * Only ever writes into a column that is still null, so a re-sent request or
 * an operator's manual correction is never clobbered by a later transition.
 * That same guard is what keeps the returned detection firing once instead of
 * on every retry.
 *
 * Returns null when nothing was stamped, when the moment was a departure
 * (only an arrival can be late), when no arrival was planned to measure
 * against, or when the delay is under the threshold. A non-null result is the
 * caller's cue to alert operators — **after its transaction commits**, so no
 * alert is ever sent for a trip update that then rolls back.
 */
export async function stampStopTransition(
  tx: Prisma.TransactionClient,
  tripId: string,
  to: TripStatus,
): Promise<DelayDetection | null> {
  const mark = STOP_MARK_BY_STATUS[to];
  if (!mark) return null;

  const now = new Date();
  const stamped = await tx.tripStop.updateMany({
    where: { tripId, stop_type: mark.stop_type, [mark.field]: null, deletedAt: null },
    data: { [mark.field]: now },
  });
  if (stamped.count === 0) return null; // already stamped — do not re-alert
  if (mark.field !== 'actual_arrival') return null;

  const stop = await tx.tripStop.findFirst({
    where: { tripId, stop_type: mark.stop_type, deletedAt: null },
    orderBy: { stop_sequence: 'asc' },
  });
  // No planned arrival means no baseline: the stop is honestly excluded from
  // delay reporting rather than counted as on time.
  if (!stop?.planned_arrival) return null;

  const delayMinutes = Math.round((now.getTime() - stop.planned_arrival.getTime()) / 60000);
  if (delayMinutes < DELAY_THRESHOLD_MINUTES) return null;

  const trip = await tx.trip.findUnique({ where: { id: tripId }, select: { ref_id: true } });
  return {
    tripId,
    tripRefId: trip?.ref_id ?? null,
    stopId: stop.id,
    stopType: mark.stop_type,
    locationName: stop.location_name,
    delayMinutes,
  };
}

/**
 * The one place a trip is marked Completed: releases the driver/vehicle back
 * to Available and generates the invoice (customer's active rate card, or the
 * kingdom-wide default, or a flat fallback) if one doesn't already exist.
 * Call from inside an existing `prisma.$transaction`.
 */
export async function completeTripAndInvoice(
  tx: Prisma.TransactionClient,
  tripId: string,
  userId: string | null | undefined,
) {
  const trip = await tx.trip.findUnique({ where: { id: tripId } });
  if (!trip) throw new Error('NOT_FOUND');

  // Marks the dropoff *departure*. Arrival was recorded when the driver
  // actually got there (the AtDelivery transition) and is deliberately not
  // backfilled here: stamping it now would date every delivery to the moment
  // its paperwork was finished, which reads as a huge delay on a trip that
  // was on time and silently erases the waiting period. A null arrival is a
  // gap the delay report can exclude honestly; a fabricated one it cannot.
  await stampStopTransition(tx, tripId, TripStatus.Completed);

  const updatedTrip = await tx.trip.update({
    where: { id: tripId },
    data: {
      status: TripStatus.Completed,
      actual_end: trip.actual_end ?? new Date(),
      updated_by: userId ?? undefined,
    },
  });

  if (trip.driverId) await tx.driver.update({ where: { id: trip.driverId }, data: { status: DriverStatus.Available } });
  if (trip.vehicleId) await tx.vehicle.update({ where: { id: trip.vehicleId }, data: { status: AssetStatus.Available } });

  const existingInvoice = await tx.invoice.findFirst({ where: { tripId: trip.id } });
  if (!existingInvoice) {
    let rateCard = await tx.rateCard.findFirst({ where: { customerId: trip.customerId, is_active: true } });
    if (!rateCard) {
      rateCard = await tx.rateCard.findFirst({ where: { customerId: null, is_active: true } });
    }

    const baseBilling = trip.billing_amount ?? (rateCard ? rateCard.base_price : 1000.0);
    const totalAmount = baseBilling + (trip.waiting_labor_charges ?? 0) + (trip.additional_stop_charges ?? 0);
    const invoiceRefId = await generateRefId('INV', () => tx.invoice.findMany({ select: { ref_id: true } }));

    await tx.invoice.create({
      data: {
        ref_id: invoiceRefId,
        tripId: trip.id,
        customerId: trip.customerId,
        status: 'Draft',
        currency: rateCard ? rateCard.currency : 'SAR',
        subtotal: baseBilling,
        total_amount: totalAmount,
        due_date: new Date(new Date().setDate(new Date().getDate() + 30)), // Net 30
        created_by: userId ?? undefined,
      },
    });
  }

  return updatedTrip;
}

