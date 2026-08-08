import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  RotateCcw,
  Plus,
  CheckCircle2,
  Navigation,
  Clock,
  ChevronRight,
  ChevronLeft,
  User,
  Truck,
  Building2,
  AlertCircle,
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import LocationPickerMap from '@/components/trips/LocationPickerMap';
import CreateDriverModal from '@/components/trips/CreateDriverModal';
import CreateVehicleModal from '@/components/trips/CreateVehicleModal';
import { tripService, CreateTripPayload } from '@/services/tripService';
import { customerService } from '@/services/customerService';
import { driverService } from '@/services/driverService';
import { vehicleService } from '@/services/vehicleService';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Combobox } from '@/components/ui/combobox';
import { Checkbox } from '@/components/ui/checkbox';
import Btn from '@/components/ui/Btn';

export default function CreateTripPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<1 | 2 | 3>(1);

  const [plannedStart, setPlannedStart] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [driverId, setDriverId] = useState('');
  const [vehicleId, setVehicleId] = useState('');
  const [assignDriverLater, setAssignDriverLater] = useState(false);
  const [assignVehicleLater, setAssignVehicleLater] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [isAddDriverOpen, setIsAddDriverOpen] = useState(false);
  const [isAddVehicleOpen, setIsAddVehicleOpen] = useState(false);

  // Stops
  const [pickupLat, setPickupLat] = useState<number | null>(24.7136); // Default Riyadh
  const [pickupLng, setPickupLng] = useState<number | null>(46.6753);
  const [pickupTime, setPickupTime] = useState('');
  const [pickupName, setPickupName] = useState('');

  const [dropoffLat, setDropoffLat] = useState<number | null>(21.5433); // Default Jeddah
  const [dropoffLng, setDropoffLng] = useState<number | null>(39.1728);
  const [dropoffTime, setDropoffTime] = useState('');
  const [dropoffName, setDropoffName] = useState('');

  // Fetch Customers, Drivers, Vehicles for Select inputs
  const { data: customersRes } = useQuery({
    queryKey: ['customers-select'],
    queryFn: () => customerService.getAll({ per_page: 100 }),
  });

  const { data: driversRes } = useQuery({
    queryKey: ['drivers-select'],
    queryFn: () => driverService.getAll({ per_page: 100, status: 'Available' }),
  });

  const { data: vehiclesRes } = useQuery({
    queryKey: ['vehicles-select'],
    queryFn: () => vehicleService.getAll({ per_page: 100, status: 'Available' }),
  });

  const customers = customersRes?.data || [];
  const drivers = driversRes?.data || [];
  const vehicles = vehiclesRes?.data || [];

  const driverOptions = drivers.map((d) => ({
    value: d.id,
    label: `${d.first_name} ${d.last_name}`,
    keywords: `${d.first_name} ${d.last_name}`,
  }));

  const vehicleOptions = vehicles.map((v) => ({
    value: v.id,
    label: `${v.plate_number} (${v.asset_type} • ${v.capacity_kg.toLocaleString()} kg)`,
    keywords: `${v.plate_number} ${v.asset_type}`,
  }));

  const selectedCustomer = customers.find(c => c.id === customerId);
  const selectedDriver = drivers.find(d => d.id === driverId);
  const selectedVehicle = vehicles.find(v => v.id === vehicleId);

  // Auto-populate locations when customer changes
  useEffect(() => {
    if (selectedCustomer) {
      if (selectedCustomer.default_pickup_lat && selectedCustomer.default_pickup_lng) {
        setPickupLat(selectedCustomer.default_pickup_lat);
        setPickupLng(selectedCustomer.default_pickup_lng);
      }
      if (selectedCustomer.default_dropoff_lat && selectedCustomer.default_dropoff_lng) {
        setDropoffLat(selectedCustomer.default_dropoff_lat);
        setDropoffLng(selectedCustomer.default_dropoff_lng);
      }
    }
  }, [selectedCustomer]);

  // Create Trip Mutation
  const createMutation = useMutation({
    mutationFn: (payload: CreateTripPayload) => tripService.create(payload),
    onSuccess: async () => {
      // Auto-save locations to customer
      if (customerId && pickupLat && pickupLng && dropoffLat && dropoffLng) {
        try {
          await customerService.update(customerId, {
            default_pickup_lat: pickupLat,
            default_pickup_lng: pickupLng,
            default_dropoff_lat: dropoffLat,
            default_dropoff_lng: dropoffLng
          });
        } catch (e) {
          console.error("Failed to auto-save locations", e);
        }
      }

      queryClient.invalidateQueries({ queryKey: ['trips'] });
      queryClient.invalidateQueries({ queryKey: ['fleet-performance'] });
      queryClient.invalidateQueries({ queryKey: ['customers-select'] });
      navigate('/trips');
    },
    onError: (err: any) => {
      setError(err.response?.data?.error?.message || err.message || 'Could not create the trip.');
    }
  });

  const handleReset = () => {
    setStep(1);
    setPlannedStart('');
    setCustomerId('');
    setDriverId('');
    setVehicleId('');
    setAssignDriverLater(false);
    setAssignVehicleLater(false);
    setPickupLat(24.7136);
    setPickupLng(46.6753);
    setPickupTime('');
    setPickupName('');
    setDropoffLat(21.5433);
    setDropoffLng(39.1728);
    setDropoffTime('');
    setDropoffName('');
    setError(null);
  };

  const nextStep = () => {
    setError(null);
    if (step === 1 && !customerId) {
      setError('Please select a customer before proceeding.');
      return;
    }
    if (step === 2 && !assignDriverLater && !driverId) {
      setError('Please assign a driver, or check "Assign driver later".');
      return;
    }
    if (step === 2 && !assignVehicleLater && !vehicleId) {
      setError('Please assign a vehicle, or check "Assign vehicle later".');
      return;
    }
    setStep((s) => (s < 3 ? (s + 1) as 1 | 2 | 3 : 3));
  };

  const prevStep = () => {
    setError(null);
    setStep((s) => (s > 1 ? (s - 1) as 1 | 2 | 3 : 1));
  };

  const missingLocation = pickupLat == null || pickupLng == null || dropoffLat == null || dropoffLng == null;
  // Names and a delivery deadline are required, not cosmetic. Without a
  // planned arrival a trip can never be judged late, so it silently vanishes
  // from delay reporting; without names the report groups by raw coordinates
  // and the same yard never accumulates a history. Both were optional, and a
  // trip created without them is quietly unreportable with nothing on screen
  // to say so.
  const missingName = pickupName.trim() === '' || dropoffName.trim() === '';
  const missingSchedule = pickupTime === '' || dropoffTime === '';
  const isFormValid =
    customerId !== '' &&
    (assignDriverLater || driverId !== '') &&
    (assignVehicleLater || vehicleId !== '') &&
    !missingLocation && !missingName && !missingSchedule;

  const handleSubmit = useCallback(() => {
    setError(null);

    if (pickupLat == null || pickupLng == null) {
      setError('Please select a pickup location on the map.');
      return;
    }
    if (dropoffLat == null || dropoffLng == null) {
      setError('Please select a dropoff location on the map.');
      return;
    }
    if (pickupName.trim() === '' || dropoffName.trim() === '') {
      setError('Name both locations (e.g. "Khamis Sorting Center") — reports group trips by these names.');
      return;
    }
    if (!pickupTime || !dropoffTime) {
      setError('Set both planned arrival times — without them this trip can never be measured for delays.');
      return;
    }

    if (pickupTime && dropoffTime && dropoffTime <= pickupTime) {
      setError('Dropoff time must be after pickup time.');
      return;
    }

    const payload: CreateTripPayload = {
      customer_id: customerId,
      driver_id: assignDriverLater ? undefined : driverId,
      vehicle_id: assignVehicleLater ? undefined : vehicleId,
      cargo_type: 'General Goods',
      planned_start: plannedStart || undefined,
      stops: [
        {
          stop_type: 'Pickup',
          lat: pickupLat,
          lng: pickupLng,
          planned_arrival: pickupTime || undefined,
          location_name: pickupName.trim() || undefined,
        },
        {
          stop_type: 'Dropoff',
          lat: dropoffLat,
          lng: dropoffLng,
          planned_arrival: dropoffTime || undefined,
          location_name: dropoffName.trim() || undefined,
        },
      ],
    };

    createMutation.mutate(payload);
  }, [customerId, driverId, vehicleId, assignDriverLater, assignVehicleLater, pickupLat, pickupLng, dropoffLat, dropoffLng, plannedStart, pickupTime, dropoffTime, pickupName, dropoffName, createMutation]);

  return (
    <DashboardLayout active="Trips" title="Create New Trip">
      <div className="mx-auto w-full max-w-4xl px-4 sm:px-6 pb-6 space-y-4 animate-fade-in">

        {/* Scope & actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-md border bg-muted px-2.5 py-1 text-xs font-semibold text-muted-foreground">
              <Building2 className="w-3.5 h-3.5" />
              MERCON Fleet
              <span className="text-muted-foreground/50">/</span>
              <span className="text-foreground font-bold">Dispatch &amp; Operations</span>
            </span>
            <Badge variant="outline" className="font-semibold">Trip Dispatch Wizard</Badge>
          </div>

          <div className="flex items-center gap-2">
            <Btn
              type="button"
              variant="outline"
              size="sm"
              onClick={() => navigate('/trips')}
              className="h-9 text-xs"
              label="Back"
              icon={<ArrowLeft className="w-3.5 h-3.5" />}
              shortcut={{ key: 'b', alt: true }}
            />
            <Button type="button" variant="ghost" size="sm" onClick={handleReset} className="h-9 text-xs gap-1.5">
              <RotateCcw className="w-3.5 h-3.5" /> Reset
            </Button>
          </div>
        </div>

        {/* Step manifest */}
        <Card className="rounded-xl overflow-hidden">
          <div className="flex flex-col md:flex-row items-center divide-y md:divide-y-0 md:divide-x">
            {/* Customer */}
            <div className={`flex-1 p-3.5 flex items-center gap-3 w-full ${step === 1 ? 'bg-muted/50' : ''}`}>
              <User className={`w-4 h-4 shrink-0 ${selectedCustomer ? 'text-primary' : 'text-muted-foreground/40'}`} />
              <div className="flex-1 min-w-0">
                <span className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground">1. Customer</span>
                <p className={`text-sm font-bold truncate mt-0.5 ${selectedCustomer ? 'text-foreground' : 'text-muted-foreground/60'}`}>
                  {selectedCustomer ? selectedCustomer.name : 'Pending...'}
                </p>
              </div>
              {selectedCustomer && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
            </div>

            {/* Assignments */}
            <div className={`flex-1 p-3.5 flex items-center gap-3 w-full ${step === 2 ? 'bg-muted/50' : ''}`}>
              <Truck className={`w-4 h-4 shrink-0 ${((selectedDriver || assignDriverLater) && (selectedVehicle || assignVehicleLater)) ? 'text-primary' : 'text-muted-foreground/40'}`} />
              <div className="flex-1 min-w-0">
                <span className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground">2. Assignments</span>
                <p className={`text-sm font-bold truncate mt-0.5 ${((selectedDriver || assignDriverLater) && (selectedVehicle || assignVehicleLater)) ? 'text-foreground' : 'text-muted-foreground/60'}`}>
                  {(selectedDriver || selectedVehicle || assignDriverLater || assignVehicleLater)
                    ? `${selectedDriver ? selectedDriver.first_name : assignDriverLater ? 'Driver later' : 'Pending...'} • ${selectedVehicle ? selectedVehicle.plate_number : assignVehicleLater ? 'Vehicle later' : 'Pending...'}`
                    : 'Pending...'}
                </p>
              </div>
              {((selectedDriver || assignDriverLater) && (selectedVehicle || assignVehicleLater)) && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
            </div>

            {/* Route */}
            <div className={`flex-1 p-3.5 flex items-center gap-3 w-full ${step === 3 ? 'bg-muted/50' : ''}`}>
              <Navigation className={`w-4 h-4 shrink-0 ${!missingLocation ? 'text-primary' : 'text-muted-foreground/40'}`} />
              <div className="flex-1 min-w-0">
                <span className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground">3. Route</span>
                <p className={`text-sm font-bold truncate mt-0.5 ${!missingLocation ? 'text-foreground' : 'text-muted-foreground/60'}`}>
                  {!missingLocation ? 'Geofences Set' : 'Pending...'}
                </p>
              </div>
              {!missingLocation && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
            </div>
          </div>
        </Card>

        {error && (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertTitle>Cannot proceed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Wizard steps */}
        {step === 1 && (
          <Card className="rounded-xl">
            <CardHeader className="border-b">
              <CardTitle className="text-sm font-bold">Step 1: Customer information</CardTitle>
              <CardDescription className="text-xs">
                Select the customer organization and specify the planned start time.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-1.5">
                <Label htmlFor="customer_id" className="text-xs font-semibold">
                  Select customer <span className="text-destructive">*</span>
                </Label>
                <Select
                  value={customerId}
                  onValueChange={(val) => {
                    setCustomerId(val);
                    setError(null);
                  }}
                >
                  <SelectTrigger id="customer_id" className="w-full">
                    <SelectValue placeholder="Choose customer organization..." />
                  </SelectTrigger>
                  <SelectContent>
                    {customers.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name} ({c.contact_phone || 'No Phone'})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="planned_start" className="text-xs font-semibold flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-muted-foreground" /> Planned start time
                </Label>
                <Input
                  id="planned_start"
                  type="datetime-local"
                  value={plannedStart}
                  onChange={(e) => setPlannedStart(e.target.value)}
                  className="font-mono max-w-sm"
                />
              </div>
            </CardContent>
            <CardFooter className="justify-end rounded-b-xl">
              <Btn
                label="Next Step"
                icon={<ChevronRight className="w-3.5 h-3.5" />}
                onClick={nextStep}
                size="sm"
                className="h-9 px-5 text-xs"
                shortcut={{ key: 'Enter', metaOrControl: true }}
              />
            </CardFooter>
          </Card>
        )}

        {step === 2 && (
          <Card className="rounded-xl">
            <CardHeader className="border-b">
              <CardTitle className="text-sm font-bold">Step 2: Driver &amp; vehicle assignment</CardTitle>
              <CardDescription className="text-xs">
                Pair an available driver with a vehicle for this trip.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="driver_id" className="text-xs font-semibold">
                      Assigned driver {!assignDriverLater && <span className="text-destructive">*</span>}
                    </Label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={assignDriverLater}
                      onClick={() => setIsAddDriverOpen(true)}
                      className="h-6 px-2 text-[11px] text-primary hover:bg-primary/10 font-medium gap-1"
                    >
                      <Plus className="w-3 h-3" /> Add driver
                    </Button>
                  </div>
                  <Combobox
                    id="driver_id"
                    value={driverId}
                    onChange={(val) => {
                      setDriverId(val);
                      setError(null);
                    }}
                    options={driverOptions}
                    placeholder="Choose available driver..."
                    searchPlaceholder="Search drivers..."
                    emptyText="No available drivers found."
                    disabled={assignDriverLater}
                  />
                  <label className="flex items-center gap-2 pt-1 cursor-pointer select-none">
                    <Checkbox
                      checked={assignDriverLater}
                      onCheckedChange={(checked) => {
                        setAssignDriverLater(checked === true);
                        if (checked) setDriverId('');
                        setError(null);
                      }}
                    />
                    <span className="text-xs text-muted-foreground">Assign driver later</span>
                  </label>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="vehicle_id" className="text-xs font-semibold">
                      Assigned vehicle {!assignVehicleLater && <span className="text-destructive">*</span>}
                    </Label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={assignVehicleLater}
                      onClick={() => setIsAddVehicleOpen(true)}
                      className="h-6 px-2 text-[11px] text-primary hover:bg-primary/10 font-medium gap-1"
                    >
                      <Plus className="w-3 h-3" /> Add vehicle
                    </Button>
                  </div>
                  <Combobox
                    id="vehicle_id"
                    value={vehicleId}
                    onChange={(val) => {
                      setVehicleId(val);
                      setError(null);
                    }}
                    options={vehicleOptions}
                    placeholder="Choose available vehicle..."
                    searchPlaceholder="Search vehicles..."
                    emptyText="No available vehicles found."
                    disabled={assignVehicleLater}
                  />
                  <label className="flex items-center gap-2 pt-1 cursor-pointer select-none">
                    <Checkbox
                      checked={assignVehicleLater}
                      onCheckedChange={(checked) => {
                        setAssignVehicleLater(checked === true);
                        if (checked) setVehicleId('');
                        setError(null);
                      }}
                    />
                    <span className="text-xs text-muted-foreground">Assign vehicle later</span>
                  </label>
                </div>
              </div>
            </CardContent>
            <CardFooter className="justify-between rounded-b-xl">
              <Btn
                variant="outline"
                onClick={prevStep}
                size="sm"
                className="h-9 px-5 text-xs"
                label="Back"
                icon={<ChevronLeft className="w-3.5 h-3.5" />}
                shortcut={{ key: 'Escape' }}
              />
              <Btn
                onClick={nextStep}
                size="sm"
                className="h-9 px-5 text-xs"
                label="Next Step"
                icon={<ChevronRight className="w-3.5 h-3.5" />}
                shortcut={{ key: 'Enter', metaOrControl: true }}
              />
            </CardFooter>
          </Card>
        )}

        {step === 3 && (
          <Card className="rounded-xl">
            <CardHeader className="border-b">
              <CardTitle className="text-sm font-bold">Step 3: Route stops &amp; geofencing</CardTitle>
              <CardDescription className="text-xs">
                Pinpoint the exact pickup and dropoff locations. Locations are auto-saved per customer.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">

              {/* Pickup Stop */}
              <div className="space-y-3 p-3.5 rounded-xl border bg-muted/30">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Pickup stop (sequence 1)
                  </span>
                  <span className="text-xs font-mono text-muted-foreground">
                    {pickupLat && pickupLng ? `${pickupLat.toFixed(4)}, ${pickupLng.toFixed(4)}` : 'Not set'}
                  </span>
                </div>

                <LocationPickerMap
                  label="Pickup Location (Click map to pin)"
                  lat={pickupLat}
                  lng={pickupLng}
                  onChange={(lat: number, lng: number) => { setPickupLat(lat); setPickupLng(lng); setError(null); }}
                  name={pickupName}
                  onNameChange={setPickupName}
                />

                <div className="space-y-1.5">
                  <Label htmlFor="pickup_time" className="text-xs font-semibold">
                    Planned pickup arrival time <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="pickup_time"
                    type="datetime-local"
                    value={pickupTime}
                    onChange={(e) => setPickupTime(e.target.value)}
                    className="font-mono max-w-sm"
                  />
                </div>
              </div>

              {/* Dropoff Stop */}
              <div className="space-y-3 p-3.5 rounded-xl border bg-muted/30">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-destructive" /> Dropoff stop (sequence 2)
                  </span>
                  <span className="text-xs font-mono text-muted-foreground">
                    {dropoffLat && dropoffLng ? `${dropoffLat.toFixed(4)}, ${dropoffLng.toFixed(4)}` : 'Not set'}
                  </span>
                </div>

                <LocationPickerMap
                  label="Dropoff Location (Click map to pin)"
                  lat={dropoffLat}
                  lng={dropoffLng}
                  onChange={(lat: number, lng: number) => { setDropoffLat(lat); setDropoffLng(lng); setError(null); }}
                  name={dropoffName}
                  onNameChange={setDropoffName}
                />

                <div className="space-y-1.5">
                  <Label htmlFor="dropoff_time" className="text-xs font-semibold">
                    Planned delivery deadline <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="dropoff_time"
                    type="datetime-local"
                    value={dropoffTime}
                    onChange={(e) => setDropoffTime(e.target.value)}
                    className="font-mono max-w-sm"
                  />
                </div>
              </div>
            </CardContent>
            <CardFooter className="justify-between rounded-b-xl">
              <Btn
                variant="outline"
                onClick={prevStep}
                size="sm"
                className="h-9 px-5 text-xs"
                label="Back"
                icon={<ChevronLeft className="w-3.5 h-3.5" />}
                shortcut={{ key: 'Escape' }}
              />
              <Btn
                onClick={handleSubmit}
                disabled={createMutation.isPending || !isFormValid}
                size="sm"
                className="h-9 px-6 text-xs"
                label={createMutation.isPending ? 'Dispatching...' : 'Dispatch Trip'}
                shortcut={{ key: 'Enter', metaOrControl: true }}
              />
            </CardFooter>
          </Card>
        )}

      </div>

      <CreateDriverModal
        isOpen={isAddDriverOpen}
        onClose={() => setIsAddDriverOpen(false)}
        onCreated={(newDriver) => { setDriverId(newDriver.id); setError(null); }}
      />
      <CreateVehicleModal
        isOpen={isAddVehicleOpen}
        onClose={() => setIsAddVehicleOpen(false)}
        onCreated={(newVehicle) => { setVehicleId(newVehicle.id); setError(null); }}
      />
    </DashboardLayout>
  );
}
