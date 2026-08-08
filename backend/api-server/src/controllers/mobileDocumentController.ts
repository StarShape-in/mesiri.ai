import { Request, Response } from 'express';
import { prisma } from '../index';

/** The logged-in driver's own documents (license, etc.), soonest-expiring first. */
export const getDriverDocuments = async (req: Request, res: Response) => {
  const driverId = (req as any).user?.driver_id;
  if (!driverId) return res.status(403).json({ success: false, error: { message: 'Driver not authenticated' } });

  try {
    const documents = await prisma.document.findMany({
      where: { entity_type: 'Driver', entity_id: driverId, deletedAt: null },
      orderBy: [{ expiry_date: 'asc' }, { createdAt: 'desc' }],
      select: {
        id: true,
        doc_type: true,
        status: true,
        file_url: true,
        mime_type: true,
        issue_date: true,
        expiry_date: true,
      },
    });

    res.json({ success: true, data: documents });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};
