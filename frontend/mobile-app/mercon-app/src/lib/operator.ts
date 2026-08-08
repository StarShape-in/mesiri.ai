/**
 * Operator data — reuses the same backend endpoints the web dashboard uses
 * (operators authenticate with role Operator, which those routes allow).
 *   GET /reports/summary  → dashboard KPIs
 *   GET /trips            → trips (filtered here to active ones)
 */
import { useCallback, useEffect, useState } from 'react';
import { api, getApiErrorMessage } from './api';
import type { TripStatus } from './trips';

export interface Kpi { value: number; delta: number | null }

export interface DashboardSummary {
  kpis: {
    total_trips: Kpi;
    active_drivers: Kpi;
    fleet_available: Kpi;
    fleet_on_trip: Kpi;
    revenue_this_month: Kpi;
    docs_expiring_soon: Kpi;
  };
  trip_status_distribution: Record<string, number>;
  monthly_revenue_chart: { month: string; revenue: number }[];
}

export interface OperatorTrip {
  id: string;
  ref_id: string | null;
  status: string;
  cargo_type: string;
  planned_start?: string | null;
  createdAt?: string;
  customer?: { name: string } | null;
  driver?: { first_name: string; last_name: string } | null;
  vehicle?: { plate_number: string } | null;
}

export interface OperatorTripStop {
  id: string;
  stop_sequence: number;
  stop_type: string;
  location_lat: number;
  location_lng: number;
  location_name: string | null;
  planned_arrival: string | null;
  actual_arrival: string | null;
  actual_departure: string | null;
}

export interface OperatorTripDetail {
  id: string;
  ref_id: string | null;
  status: TripStatus;
  cargo_type: string;
  planned_distance: number | null;
  planned_start: string | null;
  actual_start: string | null;
  planned_end: string | null;
  actual_end: string | null;
  createdAt: string;
  customer: { id: string; name: string } | null;
  driver: { id: string; first_name: string; last_name: string; phone_primary: string | null; ref_id: string | null } | null;
  vehicle: { id: string; plate_number: string; asset_type: string; ref_id: string | null } | null;
  stops: OperatorTripStop[];
}

export interface CreateTripStopInput {
  stop_type: 'Pickup' | 'Dropoff';
  lat: number;
  lng: number;
  planned_arrival?: string;
  location_name?: string;
}

export interface CreateTripInput {
  customer_id: string;
  driver_id: string;
  vehicle_id: string;
  cargo_type: string;
  planned_start?: string;
  stops: CreateTripStopInput[];
}

export interface OperatorCustomer {
  id: string;
  name: string;
  contact_phone?: string;
  credit_limit?: number;
  isActive?: boolean;
  createdAt?: string;
}

export interface CreateCustomerInput {
  name: string;
  contact_phone: string;
  credit_limit?: number;
}

export interface UpdateCustomerInput {
  name?: string;
  contact_phone?: string;
  credit_limit?: number;
  isActive?: boolean;
}

export interface OperatorDocument {
  id: string;
  entity_type: string;
  entity_id: string;
  doc_type: string;
  status: string;
  expiry_date: string | null;
}

export const ACTIVE_TRIP_STATUSES = ['Dispatched', 'AtPickup', 'InTransit', 'AtDelivery'];

export const operatorService = {
  async summary(): Promise<DashboardSummary> {
    const { data } = await api.get('/reports/summary');
    return data.data as DashboardSummary;
  },

  async activeTrips(): Promise<OperatorTrip[]> {
    const { data } = await api.get('/trips', { params: { per_page: 50 } });
    const trips = (data.data ?? []) as OperatorTrip[];
    return trips.filter((t) => ACTIVE_TRIP_STATUSES.includes(t.status));
  },

  async trips(): Promise<OperatorTrip[]> {
    const { data } = await api.get('/trips', { params: { per_page: 100 } });
    return (data.data ?? []) as OperatorTrip[];
  },

  async drivers(): Promise<OperatorDriver[]> {
    const { data } = await api.get('/drivers', { params: { per_page: 100 } });
    return (data.data ?? []) as OperatorDriver[];
  },

  async vehicles(): Promise<OperatorVehicle[]> {
    const { data } = await api.get('/vehicles', { params: { per_page: 100 } });
    return (data.data ?? []) as OperatorVehicle[];
  },

  async invoices(): Promise<OperatorInvoice[]> {
    const { data } = await api.get('/invoices', { params: { per_page: 100 } });
    return (data.data ?? []) as OperatorInvoice[];
  },

  async tripById(id: string): Promise<OperatorTripDetail> {
    const { data } = await api.get(`/trips/${id}`);
    return data.data as OperatorTripDetail;
  },

  async customers(): Promise<OperatorCustomer[]> {
    const { data } = await api.get('/customers', { params: { per_page: 100 } });
    return (data.data ?? []) as OperatorCustomer[];
  },

  async customerById(id: string): Promise<OperatorCustomer> {
    const { data } = await api.get(`/customers/${id}`);
    return data.data as OperatorCustomer;
  },

  async createCustomer(payload: CreateCustomerInput): Promise<OperatorCustomer> {
    const { data } = await api.post('/customers', payload);
    return data.data as OperatorCustomer;
  },

  async updateCustomer(id: string, payload: UpdateCustomerInput): Promise<OperatorCustomer> {
    const { data } = await api.patch(`/customers/${id}`, payload);
    return data.data as OperatorCustomer;
  },

  async availableDrivers(): Promise<OperatorDriver[]> {
    const { data } = await api.get('/drivers', { params: { per_page: 100, status: 'Available' } });
    return (data.data ?? []) as OperatorDriver[];
  },

  async availableVehicles(): Promise<OperatorVehicle[]> {
    const { data } = await api.get('/vehicles', { params: { per_page: 100, status: 'Available' } });
    return (data.data ?? []) as OperatorVehicle[];
  },

  async createTrip(payload: CreateTripInput): Promise<OperatorTripDetail> {
    const { data } = await api.post('/trips', payload);
    return data.data as OperatorTripDetail;
  },

  async vehicleDocuments(): Promise<OperatorDocument[]> {
    const { data } = await api.get('/documents', { params: { entity_type: 'Vehicle', per_page: 100 } });
    return (data.data ?? []) as OperatorDocument[];
  },

  async driverById(id: string): Promise<OperatorDriver> {
    const { data } = await api.get(`/drivers/${id}`);
    return data.data as OperatorDriver;
  },

  async vehicleById(id: string): Promise<OperatorVehicle> {
    const { data } = await api.get(`/vehicles/${id}`);
    return data.data as OperatorVehicle;
  },

  async updateDriver(id: string, payload: UpdateDriverInput): Promise<OperatorDriver> {
    const { data } = await api.patch(`/drivers/${id}`, payload);
    return data.data as OperatorDriver;
  },

  async updateVehicle(id: string, payload: UpdateVehicleInput): Promise<OperatorVehicle> {
    const { data } = await api.patch(`/vehicles/${id}`, payload);
    return data.data as OperatorVehicle;
  },

  async updateInvoiceStatus(id: string, status: string): Promise<OperatorInvoice> {
    const { data } = await api.patch(`/invoices/${id}/status`, { status });
    return data.data as OperatorInvoice;
  },

  /** Generic trip status transition — drives most of the trip lifecycle. */
  async updateTripStatus(id: string, status: string): Promise<OperatorTripDetail> {
    const { data } = await api.patch(`/trips/${id}/status`, { status });
    return data.data as OperatorTripDetail;
  },

  /** Stamps the pickup stop's actual arrival time in addition to the status change. */
  async pickupArrive(id: string): Promise<OperatorTripDetail> {
    const { data } = await api.post(`/trips/${id}/pickup/arrive`);
    return data.data as OperatorTripDetail;
  },

  async replaceDriver(id: string, newDriverId: string): Promise<OperatorTripDetail> {
    const { data } = await api.post(`/trips/${id}/replace-driver`, { new_driver_id: newDriverId });
    return data.data as OperatorTripDetail;
  },
};

export interface OperatorInvoice {
  id: string;
  ref_id: string | null;
  status: string;
  currency: string;
  total_amount: number;
  due_date: string;
  createdAt: string;
  customer?: { name: string } | null;
  trip?: { ref_id: string | null } | null;
}

export interface OperatorVehicle {
  id: string;
  ref_id: string | null;
  plate_number: string;
  asset_type: string;
  status: string;
  capacity_kg: number;
  current_odometer: number;
}

export interface OperatorDriver {
  id: string;
  ref_id: string | null;
  first_name: string;
  last_name: string;
  phone_primary: string | null;
  status: string;
  license_number: string;
  license_expiry: string;
}

export interface UpdateDriverInput {
  first_name?: string;
  last_name?: string;
  phone_primary?: string;
  license_number?: string;
  license_expiry?: string;
  status?: 'Available' | 'OnTrip' | 'OffDuty' | 'Inactive';
}

export interface UpdateVehicleInput {
  plate_number?: string;
  asset_type?: 'Flatbed' | 'Reefer' | 'Box' | 'Tanker';
  capacity_kg?: number;
  status?: 'Available' | 'OnTrip' | 'Maintenance' | 'Inactive';
}

let cacheOperatorTrips: OperatorTrip[] = [];
let isOpTripsFetched = false;

/** Forces the next `useOperatorTrips` mount/refetch to hit the API again. */
export function invalidateOperatorTrips() {
  isOpTripsFetched = false;
}

/** Loads all recent trips for the operator trip list. */
export function useOperatorTrips() {
  const [trips, setTrips] = useState<OperatorTrip[]>(cacheOperatorTrips);
  const [loading, setLoading] = useState(!isOpTripsFetched);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { showLoading?: boolean } | any) => {
    const showLoading = typeof opts === 'boolean' ? opts : typeof opts?.showLoading === 'boolean' ? opts.showLoading : !isOpTripsFetched;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await operatorService.trips();
      cacheOperatorTrips = data;
      isOpTripsFetched = true;
      setTrips(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { trips, loading, error, refetch };
}

let cacheOperatorDrivers: OperatorDriver[] = [];
let isOpDriversFetched = false;

/** Forces the next `useOperatorDrivers` mount/refetch to hit the API again. */
export function invalidateOperatorDrivers() {
  isOpDriversFetched = false;
}

/** Loads all drivers for the operator driver list. */
export function useOperatorDrivers() {
  const [drivers, setDrivers] = useState<OperatorDriver[]>(cacheOperatorDrivers);
  const [loading, setLoading] = useState(!isOpDriversFetched);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { showLoading?: boolean } | any) => {
    const showLoading = typeof opts === 'boolean' ? opts : typeof opts?.showLoading === 'boolean' ? opts.showLoading : !isOpDriversFetched;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await operatorService.drivers();
      cacheOperatorDrivers = data;
      isOpDriversFetched = true;
      setDrivers(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { drivers, loading, error, refetch };
}

let cacheOperatorVehicles: OperatorVehicle[] = [];
let isOpVehiclesFetched = false;

/** Forces the next `useOperatorVehicles` mount/refetch to hit the API again. */
export function invalidateOperatorVehicles() {
  isOpVehiclesFetched = false;
}

/** Loads all vehicles for the operator vehicle list. */
export function useOperatorVehicles() {
  const [vehicles, setVehicles] = useState<OperatorVehicle[]>(cacheOperatorVehicles);
  const [loading, setLoading] = useState(!isOpVehiclesFetched);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { showLoading?: boolean } | any) => {
    const showLoading = typeof opts === 'boolean' ? opts : typeof opts?.showLoading === 'boolean' ? opts.showLoading : !isOpVehiclesFetched;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await operatorService.vehicles();
      cacheOperatorVehicles = data;
      isOpVehiclesFetched = true;
      setVehicles(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { vehicles, loading, error, refetch };
}

export interface VehicleRenewal {
  documentId: string;
  vehiclePlate: string;
  docType: string;
  status: string;
  expiryDate: string | null;
  daysLeft: number | null;
}

/** Joins vehicle documents with their vehicle's plate number for the renewals screen. */
export function useOperatorVehicleRenewals() {
  const [renewals, setRenewals] = useState<VehicleRenewal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [documents, vehicles] = await Promise.all([
        operatorService.vehicleDocuments(),
        operatorService.vehicles(),
      ]);
      const vehicleById = new Map(vehicles.map((v) => [v.id, v]));
      const now = Date.now();
      const joined = documents.map((doc): VehicleRenewal => {
        const vehicle = vehicleById.get(doc.entity_id);
        const daysLeft = doc.expiry_date
          ? Math.ceil((new Date(doc.expiry_date).getTime() - now) / (1000 * 60 * 60 * 24))
          : null;
        return {
          documentId: doc.id,
          vehiclePlate: vehicle?.plate_number ?? 'Unknown Vehicle',
          docType: doc.doc_type,
          status: doc.status,
          expiryDate: doc.expiry_date,
          daysLeft,
        };
      });
      setRenewals(joined);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { renewals, loading, error, refetch };
}

let cacheOperatorInvoices: OperatorInvoice[] = [];
let isOpInvoicesFetched = false;

/** Forces the next `useOperatorInvoices` mount/refetch to hit the API again. */
export function invalidateOperatorInvoices() {
  isOpInvoicesFetched = false;
}

/** Loads all invoices for the operator invoice list. */
export function useOperatorInvoices() {
  const [invoices, setInvoices] = useState<OperatorInvoice[]>(cacheOperatorInvoices);
  const [loading, setLoading] = useState(!isOpInvoicesFetched);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { showLoading?: boolean } | any) => {
    const showLoading = typeof opts === 'boolean' ? opts : typeof opts?.showLoading === 'boolean' ? opts.showLoading : !isOpInvoicesFetched;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await operatorService.invoices();
      cacheOperatorInvoices = data;
      isOpInvoicesFetched = true;
      setInvoices(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { invoices, loading, error, refetch };
}

let cacheOperatorCustomers: OperatorCustomer[] = [];
let isOpCustomersFetched = false;

/** Forces the next `useOperatorCustomers` mount/refetch to hit the API again. */
export function invalidateOperatorCustomers() {
  isOpCustomersFetched = false;
}

/** Loads all customers for the operator customer list. */
export function useOperatorCustomers() {
  const [customers, setCustomers] = useState<OperatorCustomer[]>(cacheOperatorCustomers);
  const [loading, setLoading] = useState(!isOpCustomersFetched);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { showLoading?: boolean } | any) => {
    const showLoading = typeof opts === 'boolean' ? opts : typeof opts?.showLoading === 'boolean' ? opts.showLoading : !isOpCustomersFetched;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await operatorService.customers();
      cacheOperatorCustomers = data;
      isOpCustomersFetched = true;
      setCustomers(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { customers, loading, error, refetch };
}

/** Loads a single customer's detail for the operator customer edit screen. */
export function useOperatorCustomerById(id: string | undefined) {
  const [customer, setCustomer] = useState<OperatorCustomer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await operatorService.customerById(id);
      setCustomer(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { refetch(); }, [refetch]);

  return { customer, loading, error, refetch };
}

/** Loads a single trip's full detail for the operator trip details screen. */
export function useOperatorTripById(id: string | undefined) {
  const [trip, setTrip] = useState<OperatorTripDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await operatorService.tripById(id);
      setTrip(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { refetch(); }, [refetch]);

  return { trip, loading, error, refetch };
}

/** Loads a single driver's detail for the operator driver edit screen. */
export function useOperatorDriverById(id: string | undefined) {
  const [driver, setDriver] = useState<OperatorDriver | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await operatorService.driverById(id);
      setDriver(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { refetch(); }, [refetch]);

  return { driver, loading, error, refetch };
}

/** Loads a single vehicle's detail for the operator vehicle edit screen. */
export function useOperatorVehicleById(id: string | undefined) {
  const [vehicle, setVehicle] = useState<OperatorVehicle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await operatorService.vehicleById(id);
      setVehicle(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { refetch(); }, [refetch]);

  return { vehicle, loading, error, refetch };
}

let cacheOperatorSummary: DashboardSummary | null = null;
let cacheOperatorActiveTrips: OperatorTrip[] = [];
let isOpDashboardFetched = false;

/** Loads the operator dashboard (KPIs + active trips) with a manual refetch. */
export function useOperatorDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(cacheOperatorSummary);
  const [activeTrips, setActiveTrips] = useState<OperatorTrip[]>(cacheOperatorActiveTrips);
  const [loading, setLoading] = useState(!isOpDashboardFetched);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { showLoading?: boolean } | any) => {
    const showLoading = typeof opts === 'boolean' ? opts : typeof opts?.showLoading === 'boolean' ? opts.showLoading : !isOpDashboardFetched;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const [s, t] = await Promise.all([operatorService.summary(), operatorService.activeTrips()]);
      cacheOperatorSummary = s;
      cacheOperatorActiveTrips = t;
      isOpDashboardFetched = true;
      setSummary(s);
      setActiveTrips(t);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { summary, activeTrips, loading, error, refetch };
}
