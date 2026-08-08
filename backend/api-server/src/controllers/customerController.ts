import { Request, Response } from 'express';
import { prisma } from '../index';

export const getCustomers = async (req: Request, res: Response) => {
  try {
    const { is_active, search, page = '1', per_page = '20' } = req.query;
    
    const pageNumber = parseInt(page as string);
    const limit = parseInt(per_page as string);
    const skip = (pageNumber - 1) * limit;

    const whereClause: any = { deletedAt: null };
    if (is_active !== undefined) {
      whereClause.isActive = is_active === 'true';
    }
    if (search) {
      whereClause.name = { contains: search as string, mode: 'insensitive' };
    }

    const [customers, total] = await Promise.all([
      prisma.customer.findMany({
        where: whereClause,
        skip,
        take: limit,
        orderBy: { name: 'asc' },
      }),
      prisma.customer.count({ where: whereClause })
    ]);

    res.json({
      success: true,
      data: customers,
      meta: {
        page: pageNumber,
        per_page: limit,
        total,
        total_pages: Math.ceil(total / limit)
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch customers' } });
  }
};

export const getCustomerById = async (req: Request, res: Response) => {
  try {
    const customer = await prisma.customer.findUnique({
      where: { id: req.params.id as string, deletedAt: null },
      include: { trips: { take: 5, orderBy: { createdAt: 'desc' } } }
    });

    if (!customer) {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Customer not found' } });
    }

    res.json({ success: true, data: customer });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch customer' } });
  }
};

export const createCustomer = async (req: Request, res: Response) => {
  try {
    const { name, contact_phone, credit_limit } = req.body;
    
    const customer = await prisma.customer.create({
      data: {
        name,
        contact_phone,
        credit_limit: credit_limit || 0,
        created_by: (req as any).user?.id
      }
    });
    
    res.status(201).json({ success: true, data: customer });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to create customer' } });
  }
};

export const updateCustomer = async (req: Request, res: Response) => {
  try {
    const updated = await prisma.customer.update({
      where: { id: req.params.id as string },
      data: {
        ...req.body,
        updated_by: (req as any).user?.id
      }
    });
    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to update customer' } });
  }
};

export const deleteCustomer = async (req: Request, res: Response) => {
  try {
    await prisma.customer.update({
      where: { id: req.params.id as string },
      data: {
        deletedAt: new Date(),
        isActive: false,
        deleted_by: (req as any).user?.id
      }
    });
    res.json({ success: true, data: { message: 'Customer deleted successfully' } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to delete customer' } });
  }
};
