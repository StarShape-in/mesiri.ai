import rateLimit from 'express-rate-limit';

/**
 * Throttles unauthenticated, credential-guessable endpoints: login (web +
 * mobile) and password-reset requests. Without this, both are brute-forceable
 * (mobile login in particular compares a driver's license number in plaintext
 * with no per-account lockout) and password-reset can be hit repeatedly to
 * spam every Admin/Operator with notifications.
 *
 * Each call returns a fresh limiter instance — reusing one instance across
 * routes shares its counter (keyed by IP by default) between them, so
 * exhausting one endpoint's budget would also lock out an unrelated one on
 * the same IP.
 */
export const createAuthRateLimit = () => rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { success: false, error: { code: 'RATE_LIMITED', message: 'Too many attempts. Please try again later.' } },
});
