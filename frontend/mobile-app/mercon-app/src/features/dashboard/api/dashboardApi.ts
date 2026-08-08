/**
 * Dashboard API layer — raw HTTP calls only, no business logic and no shape
 * transformation beyond unwrapping the `{ success, data }` envelope. Talks to
 * the same backend the web dashboard uses (operators authenticate with role
 * Operator, which these routes allow):
 *   GET /reports/summary  → dashboard KPIs
 *   GET /reports/fleet    → per-vehicle trip counts for a date range
 *   GET /trips            → trip list
 *   GET /vehicles         → vehicle list
 *   GET /drivers          → driver list
 *   GET /documents        → document list (for the Document Expiry section)
 *   GET /notifications    → the signed-in user's notifications
 *   GET /auth/me          → the signed-in user's profile
 */
import { api } from '@/lib/api';
import type { CurrentUser, DashboardSummary, DocumentRef, DriverRef, Notification, Trip, VehicleRef } from '../types';

export interface FleetTripCount {
  id: string;
  status: VehicleRef['status'];
  total_trips: number;
}

export const dashboardApi = {
  async getSummary(): Promise<DashboardSummary> {
    const { data } = await api.get('/reports/summary');
    return data.data as DashboardSummary;
  },

  async getTrips(params: { per_page?: number; status?: string } = {}): Promise<Trip[]> {
    const { data } = await api.get('/trips', { params: { per_page: 100, ...params } });
    return (data.data ?? []) as Trip[];
  },

  async getVehicles(params: { per_page?: number } = {}): Promise<VehicleRef[]> {
    const { data } = await api.get('/vehicles', { params: { per_page: 200, ...params } });
    return (data.data ?? []) as VehicleRef[];
  },

  async getFleetTripCounts(range: { startDate: string; endDate: string }): Promise<FleetTripCount[]> {
    const { data } = await api.get('/reports/fleet', { params: { ...range, per_page: 200 } });
    return (data.data ?? []) as FleetTripCount[];
  },

  async getDrivers(params: { per_page?: number } = {}): Promise<DriverRef[]> {
    const { data } = await api.get('/drivers', { params: { per_page: 200, ...params } });
    return (data.data ?? []) as DriverRef[];
  },

  async getDocuments(params: { entity_type?: string; per_page?: number } = {}): Promise<DocumentRef[]> {
    const { data } = await api.get('/documents', { params: { per_page: 200, ...params } });
    return (data.data ?? []) as DocumentRef[];
  },

  async getNotifications(): Promise<Notification[]> {
    const { data } = await api.get('/notifications');
    return (data.data ?? []) as Notification[];
  },

  async getCurrentUser(): Promise<CurrentUser> {
    const { data } = await api.get('/auth/me');
    return data.data as CurrentUser;
  },
};
