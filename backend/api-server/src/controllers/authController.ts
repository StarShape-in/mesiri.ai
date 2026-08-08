import { Request, Response } from 'express';
import { logger } from '../utils/logger';
import { Role } from '@prisma/client';
import { env } from '../config/env';
import jwt from 'jsonwebtoken';
import bcrypt from 'bcrypt';
import { prisma } from '../index';
import { createNotification } from './notificationController';

/* ─── Unified Login (username + password) ──────────────────────────────────── */
export const login = async (req: Request, res: Response) => {
  const { username, password } = req.body; // validated by loginBody

  try {
    const user = await prisma.user.findUnique({ 
      where: { username },
      include: { driver: true } 
    });

    if (!user || !user.isActive) {
      return res.status(401).json({
        success: false,
        error: { code: 'INVALID_CREDENTIALS', message: 'Invalid username or password' }
      });
    }

    const passwordHash: string = (user as any).password_hash || '';
    const isValid = passwordHash ? await bcrypt.compare(password, passwordHash) : false;

    if (!isValid) {
      return res.status(401).json({
        success: false,
        error: { code: 'INVALID_CREDENTIALS', message: 'Invalid username or password' }
      });
    }

    const jwtPayload = { 
      id: user.id, 
      username: user.username, 
      role: user.role,
      driver_id: user.driver?.id 
    };
    
    const token = jwt.sign(jwtPayload, env.JWT_SECRET, { expiresIn: '7d' });

    return res.json({
      success: true,
      data: {
        token,
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
        user: { 
          id: user.id, 
          username: user.username, 
          role: user.role,
          name: user.name,
          driver: user.driver ? {
            id: user.driver.id,
            first_name: user.driver.first_name,
            last_name: user.driver.last_name
          } : null
        }
      }
    });
  } catch (error) {
    logger.error({ err: error }, 'Login error:');
    return res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Internal server error' } });
  }
};

/* ─── Get current profile ───────────────────────────────────────── */
export const getMe = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;

    const user = await prisma.user.findUnique({ 
      where: { id: userId },
      include: { driver: true }
    });
    
    if (!user) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'User not found' } });

    return res.json({
      success: true,
      data: {
        id: user.id,
        username: user.username,
        name: user.name,
        email: user.email,
        phone: user.phone,
        role: user.role,
        driver: user.driver ? {
          id: user.driver.id,
          first_name: user.driver.first_name,
          last_name: user.driver.last_name
        } : null
      }
    });
  } catch (error) {
    return res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Internal server error' } });
  }
};

/* ─── Update own profile (name / email / phone) ─────────────────────────────── */
export const updateMe = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { name, email, phone } = req.body;

    const data: { name?: string; email?: string | null; phone?: string | null } = {};
    if (name !== undefined) data.name = String(name).trim();
    if (email !== undefined) data.email = email ? String(email).trim() : null;
    if (phone !== undefined) data.phone = phone ? String(phone).trim() : null;

    const user = await prisma.user.update({ where: { id: userId }, data });

    return res.json({
      success: true,
      data: { id: user.id, username: user.username, name: user.name, email: user.email, phone: user.phone, role: user.role }
    });
  } catch (error: any) {
    // Unique constraint (email/phone already taken)
    if (error?.code === 'P2002') {
      return res.status(409).json({ success: false, error: { code: 'CONFLICT', message: 'That email or phone is already in use' } });
    }
    return res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to update profile' } });
  }
};

/* ─── Change own password (knows current password) ──────────────────────────── */
export const changePassword = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { current_password, new_password } = req.body;

    if (!current_password || !new_password) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'Current and new password are required' } });
    }
    if (String(new_password).length < 8) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'New password must be at least 8 characters' } });
    }

    const user = await prisma.user.findUnique({ where: { id: userId } });
    if (!user) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'User not found' } });

    const ok = user.password_hash ? await bcrypt.compare(current_password, user.password_hash) : false;
    if (!ok) return res.status(401).json({ success: false, error: { code: 'INVALID_CREDENTIALS', message: 'Current password is incorrect' } });

    const hash = await bcrypt.hash(new_password, 10);
    await prisma.user.update({ where: { id: userId }, data: { password_hash: hash } });

    return res.json({ success: true, data: { message: 'Password updated' } });
  } catch (error) {
    return res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to change password' } });
  }
};

/* ─── Request a password reset: notify every Admin + Operator ────────────────── */
export const requestPasswordReset = async (req: Request, res: Response) => {
  try {
    const { identifier } = req.body;
    const who = identifier ? String(identifier).trim() : 'A user';

    const staff = await prisma.user.findMany({
      where: { role: { in: [Role.Admin, Role.Operator] }, isActive: true, deletedAt: null },
      select: { id: true },
    });

    await Promise.all(
      staff.map((u) =>
        createNotification(
          u.id,
          'Password Reset Request',
          `${who} requested a password reset. Reset it in User Management (web users) or the Drivers module (drivers).`,
          'Security',
        ),
      ),
    );

    // Generic response — don't reveal whether the identifier matched an account.
    return res.json({ success: true, data: { message: 'Your operator and admin have been notified.' } });
  } catch (error) {
    return res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to submit request' } });
  }
};

