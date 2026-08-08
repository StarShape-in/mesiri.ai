import express, { Request, Response } from 'express';
import { logger } from './utils/logger';
import { createServer } from 'http';
import { Server, Socket } from 'socket.io';
import cors from 'cors';
import jwt from 'jsonwebtoken';
import { PrismaClient } from '@prisma/client';
import { env } from './config/env';

const app = express();
const httpServer = createServer(app);
// CORS origin is left open here (tightened for the HTTP API in Phase 3) —
// authentication below is what actually gates access to this socket server.
export const io = new Server(httpServer, {
  cors: { origin: '*', methods: ['GET', 'POST', 'PATCH'] }
});

const port = env.PORT;
export const prisma = new PrismaClient();

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

interface SocketUser {
  id?: string;
  driver_id?: string;
  role?: 'Admin' | 'Operator' | 'Driver';
}

import authRoutes from './routes/authRoutes';
import driverRoutes from './routes/driverRoutes';
import vehicleRoutes from './routes/vehicleRoutes';
import customerRoutes from './routes/customerRoutes';
import tripRoutes from './routes/tripRoutes';
import invoiceRoutes from './routes/invoiceRoutes';
import maintenanceRoutes from './routes/maintenanceRoutes';
import documentRoutes from './routes/documentRoutes';
import reportsRoutes from './routes/reportsRoutes';
import mobileAuthRoutes from './routes/mobileAuthRoutes';
import mobileTripRoutes from './routes/mobileTripRoutes';
import mobileNotificationRoutes from './routes/mobileNotificationRoutes';
import mobileProfileRoutes from './routes/mobileProfileRoutes';
import mobileEmergencyRoutes from './routes/mobileEmergencyRoutes';
import mobileMiscRoutes from './routes/mobileMiscRoutes';
import rateCardRoutes from './routes/rateCardRoutes';
import notificationRoutes from './routes/notificationRoutes';
import uploadRoutes from './routes/uploadRoutes';
import userRoutes from './routes/userRoutes';
import { initCronJobs } from './services/cronJobs';

import helmet from 'helmet';

// Middleware
const allowedOrigins = [
  'http://localhost:3000',
  'http://localhost:3060',
  process.env.VITE_APP_URL || 'https://dashboard.mercon.local'
];

app.use(cors({
  origin: (origin, callback) => {
    callback(null, true);
  },
  credentials: true
}));

app.use(helmet());
app.use(helmet.hsts({
  maxAge: 31536000,
  includeSubDomains: true,
  preload: true
}));

app.use(express.json());
app.use('/uploads', express.static('uploads')); // Serve uploaded files statically

// Routes
app.use('/auth', authRoutes);
app.use('/drivers', driverRoutes);
app.use('/vehicles', vehicleRoutes);
app.use('/customers', customerRoutes);
app.use('/trips', tripRoutes);
app.use('/invoices', invoiceRoutes);
app.use('/maintenance', maintenanceRoutes);
app.use('/reports', reportsRoutes);
app.use('/documents', documentRoutes);
app.use('/rate-cards', rateCardRoutes);
app.use('/notifications', notificationRoutes);
app.use('/upload', uploadRoutes);
app.use('/users', userRoutes);

// Mobile API Routes
app.use('/mobile/auth', mobileAuthRoutes);
app.use('/mobile/trips', mobileTripRoutes);
app.use('/mobile/notifications', mobileNotificationRoutes);
app.use('/mobile/profile', mobileProfileRoutes);
app.use('/mobile/emergency', mobileEmergencyRoutes);
app.use('/mobile', mobileMiscRoutes); // /mobile/documents, /mobile/vehicle

// Socket.io Telemetry WebSockets — every connection must present a valid JWT
// (same token used for the HTTP API) in the handshake, or it's rejected.
io.use((socket, next) => {
  const token = socket.handshake.auth?.token;
  if (!token) return next(new Error('Authentication required'));

  jwt.verify(token, env.JWT_SECRET, (err: jwt.VerifyErrors | null, decoded: any) => {
    if (err || !decoded) return next(new Error('Invalid or expired token'));
    (socket.data as { user: SocketUser }).user = decoded as SocketUser;
    next();
  });
});

io.on('connection', (socket: Socket) => {
  const user = (socket.data as { user: SocketUser }).user;
  logger.info(`📡 WebSocket connected: ${socket.id} (${user.role ?? 'unknown'})`);

  // Auto-join a private room for this identity so server-sent notifications
  // (createNotification/createDriverNotification) can target them directly
  // instead of broadcasting to every connected client.
  if (user.role === 'Driver' && user.driver_id) {
    socket.join(`driver:${user.driver_id}`);
  } else if (user.id) {
    socket.join(`user:${user.id}`);
  }

  // A dashboard (Admin/Operator) or the assigned driver asks to watch a
  // specific trip's live location. Only the assigned driver or an
  // Admin/Operator may join — never an arbitrary authenticated client.
  socket.on('join:trip', async (tripId: unknown) => {
    if (typeof tripId !== 'string' || !UUID_RE.test(tripId)) return;

    if (user.role === 'Admin' || user.role === 'Operator') {
      socket.join(`trip:${tripId}`);
      return;
    }
    if (user.role === 'Driver' && user.driver_id) {
      const trip = await prisma.trip.findUnique({ where: { id: tripId }, select: { driverId: true } });
      if (trip?.driverId === user.driver_id) socket.join(`trip:${tripId}`);
    }
  });

  // Driver sends a GPS update. Only accepted from the driver actually
  // assigned to that trip, and relayed only to that trip's room — not to
  // every connected client.
  socket.on('driver:location_update', async (data) => {
    if (user.role !== 'Driver' || !user.driver_id) return;
    if (!data || typeof data.tripId !== 'string' || data.driverId !== user.driver_id) return;

    const trip = await prisma.trip.findUnique({ where: { id: data.tripId }, select: { driverId: true } });
    if (trip?.driverId !== user.driver_id) return;

    io.to(`trip:${data.tripId}`).emit(`trip:location_update:${data.tripId}`, data);
  });

  socket.on('disconnect', () => {
    logger.info(`📡 WebSocket disconnected: ${socket.id}`);
  });
});

// Healthcheck endpoint
app.get('/health', (req: Request, res: Response) => {
  res.json({ success: true, message: 'MERCON API is running perfectly!' });
});

// Catches errors passed via next(err) — most notably multer's fileFilter
// rejections (invalid upload type). Must be registered after all routes.
// Without this, Express's default handler returns a raw HTML page with a
// full stack trace and a misleading 500 for what's really a 400-level
// client error.
app.use((err: Error, req: Request, res: Response, next: express.NextFunction) => {
  if (res.headersSent) return next(err);
  logger.error({ err }, 'Unhandled request error');
  res.status(400).json({ success: false, error: { code: 'BAD_REQUEST', message: err.message || 'Invalid request' } });
});

// Initialize Background Workers
initCronJobs();

httpServer.listen(port, () => {
  logger.info(`🚀 MERCON API Server (with WebSockets) is running on port ${port}`);
});
