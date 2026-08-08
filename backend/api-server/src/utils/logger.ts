/**
 * Centralized structured logger (Pino).
 * - Development: pretty, colorized, human-readable output.
 * - Production: single-line JSON (ready for log aggregators).
 *
 * Usage:  import { logger } from '../utils/logger';
 *         logger.info({ userId }, 'User logged in');
 *         logger.error({ err }, 'Something failed');
 */
import pino from 'pino';

const isProd = process.env.NODE_ENV === 'production';

export const logger = pino({
  level: process.env.LOG_LEVEL ?? (isProd ? 'info' : 'debug'),
  // Pretty transport only in development; production stays as raw JSON on stdout.
  transport: isProd
    ? undefined
    : {
        target: 'pino-pretty',
        options: { colorize: true, translateTime: 'SYS:HH:MM:ss', ignore: 'pid,hostname' },
      },
});
