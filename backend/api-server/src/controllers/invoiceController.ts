import { Request, Response } from 'express';
import { prisma } from '../index';
import { generateRefId } from '../utils/refId';
import { InvoiceStatus } from '@prisma/client';

export const getInvoices = async (req: Request, res: Response) => {
  try {
    const { status, customer_id, search, page = '1', per_page = '20' } = req.query;

    const pageNumber = parseInt(page as string);
    const limit = parseInt(per_page as string);
    const skip = (pageNumber - 1) * limit;

    const whereClause: any = { deletedAt: null };
    if (status) whereClause.status = status as InvoiceStatus;
    if (customer_id) whereClause.customerId = customer_id as string;
    if (search) {
      whereClause.OR = [
        { ref_id: { contains: search as string, mode: 'insensitive' } },
        { customer: { name: { contains: search as string, mode: 'insensitive' } } },
      ];
    }

    const [invoices, total] = await Promise.all([
      prisma.invoice.findMany({
        where: whereClause,
        skip,
        take: limit,
        orderBy: { createdAt: 'desc' },
        include: { customer: true, trip: true }
      }),
      prisma.invoice.count({ where: whereClause })
    ]);

    res.json({
      success: true,
      data: invoices,
      meta: {
        page: pageNumber,
        per_page: limit,
        total,
        total_pages: Math.ceil(total / limit)
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch invoices' } });
  }
};

export const createInvoice = async (req: Request, res: Response) => {
  try {
    const { trip_id, customer_id, subtotal, total_amount, due_date } = req.body; // validated & coerced by createInvoiceBody

    const ref_id = await generateRefId('INV', () =>
      prisma.invoice.findMany({ select: { ref_id: true } }));

    const invoice = await prisma.invoice.create({
      data: {
        ref_id,
        tripId: trip_id,
        customerId: customer_id,
        subtotal,
        total_amount,
        due_date,
        status: InvoiceStatus.Draft,
        created_by: (req as any).user?.id
      }
    });

    res.status(201).json({ success: true, data: invoice });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to create invoice' } });
  }
};

export const getInvoiceById = async (req: Request, res: Response) => {
  try {
    const invoice = await prisma.invoice.findUnique({
      where: { id: req.params.id as string, deletedAt: null },
      include: { customer: true, trip: true }
    });
    if (!invoice) {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Invoice not found' } });
    }
    res.json({ success: true, data: invoice });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch invoice' } });
  }
};

export const updateInvoiceStatus = async (req: Request, res: Response) => {
  try {
    const { status } = req.body;

    const allowedStatuses = Object.values(InvoiceStatus);
    if (!status || !allowedStatuses.includes(status as InvoiceStatus)) {
      return res.status(400).json({
        success: false,
        error: { code: 'VALIDATION_ERROR', message: `Status must be one of: ${allowedStatuses.join(', ')}` }
      });
    }

    const updated = await prisma.invoice.update({
      where: { id: req.params.id as string },
      data: {
        status: status as InvoiceStatus,
        updated_by: (req as any).user?.id
      },
      include: { customer: true, trip: true }
    });

    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to update invoice status' } });
  }
};


export const bulkDeleteInvoices = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'No IDs provided' } });
    }

    await prisma.invoice.updateMany({
      where: { id: { in: ids } },
      data: {
        deletedAt: new Date(),
        isActive: false,
        deleted_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully deleted ${ids.length} invoices` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk delete invoices` } });
  }
};

export const bulkUpdateInvoiceStatus = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids, status } = req.body;

    if (!Array.isArray(ids) || ids.length === 0 || !status) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'IDs and status are required' } });
    }

    await prisma.invoice.updateMany({
      where: { id: { in: ids } },
      data: {
        status: status as InvoiceStatus,
        updated_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully updated ${ids.length} invoices` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk update invoices` } });
  }
};
