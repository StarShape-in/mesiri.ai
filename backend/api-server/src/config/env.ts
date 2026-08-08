/**
 * Centralized environment configuration.
 * Loads .env once and fails fast on missing required variables —
 * no silent fallbacks for secrets.
 */
import dotenv from 'dotenv';

dotenv.config();

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const env = {
  DATABASE_URL: required('DATABASE_URL'),
  JWT_SECRET: required('JWT_SECRET'),
  PORT: Number(process.env.PORT) || 3000,
  BASE_URL: process.env.BASE_URL, // optional — derived from PORT when absent
  ICCES_USER: process.env.ICCES_USER || 'demo',
  ICCES_PASS: process.env.ICCES_PASS || 'demo123',
  ICCES_ACCT: process.env.ICCES_ACCT || 'demo_account',
};
