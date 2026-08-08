import { Request, Response } from 'express';
import { prisma } from '../index';

export const getMobileNotifications = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });

  try {
    const notifications = await prisma.notification.findMany({
      where: { driverId },
      orderBy: { createdAt: 'desc' },
      take: 50,
    });

    res.json({ success: true, data: notifications });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

export const markMobileNotificationRead = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  const id = req.params.id as string;
  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });

  try {
    // Scope the update to this driver's own notifications.
    const notification = await prisma.notification.findFirst({ where: { id, driverId } });
    if (!notification) return res.status(404).json({ success: false, error: { message: 'Notification not found' } });

    const updated = await prisma.notification.update({ where: { id }, data: { is_read: true } });
    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};
