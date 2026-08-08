import { Request, Response } from 'express';
import { logger } from '../utils/logger';
import { prisma } from '../index';
import bcrypt from 'bcrypt';

// Get all users (except drivers if we only want dashboard users, but let's just return all non-drivers for now, or all)
export const getUsers = async (req: Request, res: Response) => {
  try {
    const users = await prisma.user.findMany({
      where: { role: { not: 'Driver' } },
      select: {
        id: true,
        name: true,
        email: true,
        username: true,
        role: true,
        isActive: true,
        createdAt: true,
      },
      orderBy: { createdAt: 'desc' }
    });
    
    // Map to frontend expected format
    const formattedUsers = users.map(u => ({
      ...u,
      status: u.isActive ? 'Active' : 'Inactive',
      lastLogin: u.createdAt.toISOString(), // Placeholder since lastLogin is missing
    }));

    res.json({ success: true, data: formattedUsers });
  } catch (error) {
    logger.error({ err: error }, 'Error fetching users:');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Internal server error' } });
  }
};

// Create a new user
export const createUser = async (req: Request, res: Response) => {
  try {
    const { name, email, role, password } = req.body;
    
    if (!name || !email || !role || !password) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'Missing required fields' } });
    }

    const existingUser = await prisma.user.findFirst({
      where: { OR: [{ email }, { username: email }] }
    });

    if (existingUser) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'User with this email already exists' } });
    }

    const password_hash = await bcrypt.hash(password, 10);

    const newUser = await prisma.user.create({
      data: {
        name,
        email,
        username: email, // use email as username for simplicity
        role,
        password_hash,
        isActive: true
      }
    });

    res.json({
      success: true,
      data: { id: newUser.id, name: newUser.name, email: newUser.email, role: newUser.role, status: 'Active' }
    });
  } catch (error) {
    logger.error({ err: error }, 'Error creating user:');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Internal server error' } });
  }
};

// Update an existing user
export const updateUser = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { name, email, role, status, password } = req.body;

    const dataToUpdate: any = {};
    if (name) dataToUpdate.name = name;
    if (email) {
      dataToUpdate.email = email;
      dataToUpdate.username = email;
    }
    if (role) dataToUpdate.role = role;
    if (status) dataToUpdate.isActive = status === 'Active';
    if (password) {
      dataToUpdate.password_hash = await bcrypt.hash(password, 10);
    }

    const updatedUser = await prisma.user.update({
      where: { id: id as string },
      data: dataToUpdate
    });

    res.json({
      success: true,
      data: { id: updatedUser.id, name: updatedUser.name, email: updatedUser.email, role: updatedUser.role, status: updatedUser.isActive ? 'Active' : 'Inactive' }
    });
  } catch (error) {
    logger.error({ err: error }, 'Error updating user:');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Internal server error' } });
  }
};

// Delete (Hard delete or soft delete) a user
export const deleteUser = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    
    // Check if it's the current user trying to delete themselves
    if ((req as any).user?.id === id) {
       return res.status(403).json({ success: false, error: { code: 'FORBIDDEN', message: 'Cannot delete your own account' } });
    }

    // Soft delete (deactivate) for safety
    await prisma.user.update({
      where: { id: id as string },
      data: { isActive: false, deletedAt: new Date() }
    });

    res.json({ success: true, message: 'User deactivated successfully' });
  } catch (error) {
    logger.error({ err: error }, 'Error deleting user:');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Internal server error' } });
  }
};
