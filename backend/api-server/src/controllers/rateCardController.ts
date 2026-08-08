import { Request, Response } from 'express';
import { prisma } from '../index';

export const createRateCard = async (req: Request, res: Response) => {
  try {
    const { name, route_origin, route_destination, base_price, currency, customerId, is_active } = req.body;
    const userId = (req as any).user?.id;

    const rateCard = await prisma.rateCard.create({
      data: {
        name,
        route_origin,
        route_destination,
        base_price: Number(base_price),
        currency: currency || 'SAR',
        customerId: customerId || null,
        is_active: is_active ?? true,
        created_by: userId,
      }
    });
    res.status(201).json({ success: true, data: rateCard });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

export const getRateCards = async (req: Request, res: Response) => {
  try {
    const { customerId, active_only } = req.query;
    
    const whereClause: any = { deletedAt: null };
    if (customerId) whereClause.customerId = customerId as string;
    if (active_only === 'true') whereClause.is_active = true;

    const rateCards = await prisma.rateCard.findMany({
      where: whereClause,
      include: {
        customer: { select: { id: true, name: true } }
      },
      orderBy: { createdAt: 'desc' }
    });
    res.json({ success: true, data: rateCards });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

export const getRateCardById = async (req: Request, res: Response) => {
  try {
    const rateCard = await prisma.rateCard.findUnique({
      where: { id: req.params.id as string },
      include: { customer: { select: { id: true, name: true } } }
    });
    if (!rateCard || rateCard.deletedAt) {
      return res.status(404).json({ success: false, error: { message: 'RateCard not found' } });
    }
    res.json({ success: true, data: rateCard });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

export const updateRateCard = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { name, route_origin, route_destination, base_price, currency, customerId, is_active } = req.body;
    const userId = (req as any).user?.id;

    const existing = await prisma.rateCard.findUnique({ where: { id: id as string } });
    if (!existing || existing.deletedAt) {
      return res.status(404).json({ success: false, error: { message: 'RateCard not found' } });
    }

    const updated = await prisma.rateCard.update({
      where: { id: id as string },
      data: {
        name,
        route_origin,
        route_destination,
        base_price: base_price !== undefined ? Number(base_price) : undefined,
        currency,
        customerId: customerId === null ? null : customerId || undefined,
        is_active,
        updated_by: userId,
        version: existing.version + 1
      }
    });
    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};

export const deleteRateCard = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = (req as any).user?.id;

    await prisma.rateCard.update({
      where: { id: id as string },
      data: { deletedAt: new Date(), deleted_by: userId as string, is_active: false }
    });
    res.json({ success: true, message: 'RateCard deleted successfully' });
  } catch (error) {
    res.status(500).json({ success: false, error: { message: 'Internal server error' } });
  }
};


export const bulkDeleteRateCards = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'No IDs provided' } });
    }

    await prisma.rateCard.updateMany({
      where: { id: { in: ids } },
      data: {
        deletedAt: new Date(),
        is_active: false,
        deleted_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully deleted ${ids.length} ratecards` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk delete ratecards` } });
  }
};
