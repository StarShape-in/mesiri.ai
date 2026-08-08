import { Request, Response } from 'express';
import { Role } from '@prisma/client';
import { logger } from '../utils/logger';
import { prisma, io } from '../index';
import type { DelayDetection } from '../services/tripLifecycle';

export const getNotifications = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    if (!userId) return res.status(401).json({ success: false, error: { message: 'Unauthorized' } });

    const notifications = await prisma.notification.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 50 // Limit to recent 50
    });

    res.json({ success: true, data: notifications });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

export const markAsRead = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = (req as any).user?.id;

    const notification = await prisma.notification.findFirst({
      where: { id: id as string, userId: userId as string }
    });

    if (!notification) {
      return res.status(404).json({ success: false, error: { message: 'Notification not found' } });
    }

    const updated = await prisma.notification.update({
      where: { id: id as string },
      data: { is_read: true }
    });

    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

export const sendBulkCommunication = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { entity_type, ids, method, subject, message } = req.body;

    if (!Array.isArray(ids) || ids.length === 0 || !method || !message) {
      return res.status(400).json({ success: false, error: { message: 'Validation error: Missing fields' } });
    }

    // In a real scenario, this would integrate with SendGrid or Twilio
    logger.info(`[SIMULATION] Sending ${method} to ${ids.length} ${entity_type}s. Subject: ${subject}`);
    
    // We can also create a notification for the current user confirming the batch sent
    if (userId) {
      await createNotification(
        userId,
        `Bulk ${method} Sent`,
        `Successfully sent communication to ${ids.length} ${entity_type}(s).`,
        'system'
      );
    }

    res.json({ success: true, data: { message: `Simulated sending ${method} to ${ids.length} recipients` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Failed to send bulk communication' } });
  }
};

export const createNotification = async (
  userId: string, 
  title: string, 
  message: string, 
  type: string, 
  entity_type?: string, 
  entity_id?: string
) => {
  try {
    const notification = await prisma.notification.create({
      data: {
        userId,
        title,
        message,
        type,
        entity_type,
        entity_id
      }
    });

    // Send to just this user's private room (they auto-join it on socket connect)
    io.to(`user:${userId}`).emit(`user:notification:${userId}`, notification);

    return notification;
  } catch (error) {
    logger.error({ err: error }, 'Failed to create notification');
  }
};

/** "2h 35m" — how a dispatcher would say it, not 155 minutes. */
function formatDelay(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

/**
 * Tell every active Admin and Operator that a stop was reached late, so the
 * reason can be logged while the driver is still reachable and remembers it.
 *
 * Broadcast rather than assigned: there is no concept of who is on shift, and
 * inventing one would be more machinery than this needs. Whoever is at a
 * screen picks it up, and because the flag is driven by `delay_reason` being
 * null, the first operator to log a reason clears it for everyone — two
 * people cannot both spend time on the same delay.
 *
 * A new Operator account is included automatically from the day it is created;
 * nothing here needs updating as the team grows.
 *
 * Best-effort by design: a notification that fails must never roll back or
 * obscure the trip update that triggered it. Mirrors the emergency broadcast
 * in mobileEmergencyController.
 */
export const notifyOperatorsOfDelay = async (detection: DelayDetection) => {
  try {
    const staff = await prisma.user.findMany({
      where: { role: { in: [Role.Admin, Role.Operator] }, isActive: true, deletedAt: null },
      select: { id: true },
    });
    if (staff.length === 0) return;

    const where = detection.locationName ?? (detection.stopType === 'Pickup' ? 'pickup' : 'delivery');
    const trip = detection.tripRefId ?? 'A trip';
    const message =
      `${trip} reached ${where} ${formatDelay(detection.delayMinutes)} late. ` +
      `Log the reason while the driver still remembers it.`;

    await Promise.all(
      staff.map((u) =>
        createNotification(u.id, 'Trip Delayed', message, 'Delay', 'Trip', detection.tripId),
      ),
    );
  } catch (error) {
    logger.error({ err: error, tripId: detection.tripId }, 'Failed to notify operators of delay');
  }
};

/** Create a notification addressed to a Driver (mobile). Mirrors createNotification
 *  but keys off driverId instead of userId. */
export const createDriverNotification = async (
  driverId: string,
  title: string,
  message: string,
  type: string,
  entity_type?: string,
  entity_id?: string
) => {
  try {
    const notification = await prisma.notification.create({
      data: { driverId, title, message, type, entity_type, entity_id }
    });

    io.to(`driver:${driverId}`).emit(`driver:notification:${driverId}`, notification);

    return notification;
  } catch (error) {
    logger.error({ err: error }, 'Failed to create driver notification');
  }
};
