import { Request, Response } from 'express';
import { logger } from '../utils/logger';
import jwt from 'jsonwebtoken';
import { prisma } from '../index';
import { env } from '../config/env';

export const mobileLogin = async (req: Request, res: Response) => {
  const { phone_primary, license_number } = req.body;

  if (!phone_primary || !license_number) {
    return res.status(400).json({
      success: false,
      error: { code: 'VALIDATION_ERROR', message: 'Phone and License Number are required' }
    });
  }

  try {
    const driver = await prisma.driver.findUnique({
      where: { phone_primary },
    });

    if (!driver || !driver.isActive) {
      return res.status(401).json({
        success: false,
        error: { code: 'INVALID_CREDENTIALS', message: 'Invalid credentials or inactive account' }
      });
    }

    // For MVP, we simply use the license_number as a plaintext password match
    // In production, drivers should have a hashed PIN or SMS OTP.
    if (driver.license_number !== license_number) {
      return res.status(401).json({
        success: false,
        error: { code: 'INVALID_CREDENTIALS', message: 'Invalid credentials' }
      });
    }

    const token = jwt.sign(
      { 
        id: driver.id, 
        driver_id: driver.id,
        role: 'Driver' 
      },
      env.JWT_SECRET,
      { expiresIn: '30d' }
    );

    res.json({
      success: true,
      data: {
        token,
        driver: {
          id: driver.id,
          name: `${driver.first_name} ${driver.last_name}`,
          ref_id: driver.ref_id,
          status: driver.status
        }
      }
    });
  } catch (error) {
    logger.error({ err: error }, 'Mobile login error:');
    res.status(500).json({
      success: false,
      error: { code: 'SERVER_ERROR', message: 'Internal server error' }
    });
  }
};
