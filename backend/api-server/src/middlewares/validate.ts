import { Request, Response, NextFunction } from 'express';
import { ZodError, ZodType } from 'zod';

interface Schemas {
  body?: ZodType;
  params?: ZodType;
  query?: ZodType;
}

/**
 * Reusable request-validation middleware backed by Zod.
 * Validates (and coerces) body / params / query, replacing each with the parsed
 * value so downstream controllers get typed, NaN-free data. Returns a consistent
 * 400 error envelope on failure.
 *
 * Express 5 exposes `query`/`params` as getters, so we redefine them rather than
 * assign.
 */
export const validate =
  (schemas: Schemas) =>
  (req: Request, res: Response, next: NextFunction) => {
    try {
      if (schemas.body) req.body = schemas.body.parse(req.body);
      if (schemas.params) {
        Object.defineProperty(req, 'params', { value: schemas.params.parse(req.params), writable: true, configurable: true });
      }
      if (schemas.query) {
        Object.defineProperty(req, 'query', { value: schemas.query.parse(req.query), writable: true, configurable: true });
      }
      next();
    } catch (err) {
      if (err instanceof ZodError) {
        return res.status(400).json({
          success: false,
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Invalid request data',
            details: err.issues.map((i) => ({ path: i.path.join('.'), message: i.message })),
          },
        });
      }
      next(err);
    }
  };
