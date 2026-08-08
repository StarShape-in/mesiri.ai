import { Request, Response } from 'express';
import { env } from '../config/env';
import { prisma } from '../index';
import { DocType, DocStatus } from '@prisma/client';
import path from 'path';

/* ─── List documents ──────────────────────────────────────────────────────── */
export const getDocuments = async (req: Request, res: Response) => {
  try {
    const {
      entity_type,
      entity_id,
      doc_type,
      status,
      expiring_within_days,
      page = '1',
      per_page = '20'
    } = req.query;

    const pageNumber = parseInt(page as string);
    const limit = parseInt(per_page as string);
    const skip = (pageNumber - 1) * limit;

    const whereClause: any = { deletedAt: null };
    if (entity_type) whereClause.entity_type = entity_type as string;
    if (entity_id)   whereClause.entity_id = entity_id as string;
    if (doc_type)    whereClause.doc_type = doc_type as DocType;
    if (status)      whereClause.status = status as DocStatus;

    // Filter by expiry window (e.g. docs expiring within 30 days)
    if (expiring_within_days) {
      const days = parseInt(expiring_within_days as string);
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() + days);
      whereClause.expiry_date = { lte: cutoff, gte: new Date() };
    }

    const [documents, total] = await Promise.all([
      prisma.document.findMany({
        where: whereClause,
        skip,
        take: limit,
        orderBy: { createdAt: 'desc' }
      }),
      prisma.document.count({ where: whereClause })
    ]);

    res.json({
      success: true,
      data: documents,
      meta: {
        page: pageNumber,
        per_page: limit,
        total,
        total_pages: Math.ceil(total / limit)
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch documents' } });
  }
};

/* ─── Get single document ─────────────────────────────────────────────────── */
export const getDocumentById = async (req: Request, res: Response) => {
  try {
    const document = await prisma.document.findUnique({
      where: { id: req.params.id as string, deletedAt: null }
    });
    if (!document) {
      return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Document not found' } });
    }
    res.json({ success: true, data: document });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to fetch document' } });
  }
};

/* ─── Upload document ─────────────────────────────────────────────────────── */
export const uploadDocument = async (req: Request, res: Response) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        error: { code: 'VALIDATION_ERROR', message: 'No file uploaded' }
      });
    }

    const { entity_type, entity_id, doc_type, issue_date, expiry_date, is_confidential } = req.body;

    if (!entity_type || !entity_id || !doc_type) {
      return res.status(400).json({
        success: false,
        error: { code: 'VALIDATION_ERROR', message: 'entity_type, entity_id, and doc_type are required' }
      });
    }

    // Build the public URL for the uploaded file
    const baseUrl = env.BASE_URL || `http://localhost:${env.PORT}`;
    const file_url = `${baseUrl}/uploads/${req.file.filename}`;

    const document = await prisma.document.create({
      data: {
        entity_type,
        entity_id,
        doc_type: doc_type as DocType,
        status: DocStatus.PendingReview,
        file_url,
        mime_type: req.file.mimetype,
        issue_date: issue_date ? new Date(issue_date) : null,
        expiry_date: expiry_date ? new Date(expiry_date) : null,
        is_confidential: is_confidential === 'true',
        created_by: (req as any).user?.id
      }
    });

    res.status(201).json({ success: true, data: document });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to upload document' } });
  }
};

/* ─── Update document status (verify / reject) ────────────────────────────── */
export const updateDocumentStatus = async (req: Request, res: Response) => {
  try {
    const { status, expiry_date } = req.body;

    const allowedStatuses = Object.values(DocStatus);
    if (!status || !allowedStatuses.includes(status as DocStatus)) {
      return res.status(400).json({
        success: false,
        error: { code: 'VALIDATION_ERROR', message: `Status must be one of: ${allowedStatuses.join(', ')}` }
      });
    }

    const updateData: any = {
      status: status as DocStatus,
      updated_by: (req as any).user?.id
    };

    if (status === DocStatus.Verified) {
      updateData.verified_by = (req as any).user?.id;
    }
    if (expiry_date) {
      updateData.expiry_date = new Date(expiry_date);
    }

    const updated = await prisma.document.update({
      where: { id: req.params.id as string },
      data: updateData
    });

    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to update document status' } });
  }
};

/* ─── Delete document (soft) ──────────────────────────────────────────────── */
export const deleteDocument = async (req: Request, res: Response) => {
  try {
    await prisma.document.update({
      where: { id: req.params.id as string },
      data: {
        deletedAt: new Date(),
        isActive: false,
        deleted_by: (req as any).user?.id
      }
    });
    res.json({ success: true, data: { message: 'Document deleted successfully' } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to delete document' } });
  }
};


export const bulkDeleteDocuments = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'No IDs provided' } });
    }

    await prisma.document.updateMany({
      where: { id: { in: ids } },
      data: {
        deletedAt: new Date(),
        isActive: false,
        deleted_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully deleted ${ids.length} documents` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk delete documents` } });
  }
};

export const bulkUpdateDocumentStatus = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids, status } = req.body;

    if (!Array.isArray(ids) || ids.length === 0 || !status) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'IDs and status are required' } });
    }

    await prisma.document.updateMany({
      where: { id: { in: ids } },
      data: {
        status: status as DocStatus,
        updated_by: userId
      }
    });
    res.json({ success: true, data: { message: `Successfully updated ${ids.length} documents` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: `Failed to bulk update documents` } });
  }
};
