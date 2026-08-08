import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Save, HelpCircle, Truck, UserCheck, CheckCircle2, Clock, AlertTriangle, ShieldCheck, RefreshCw } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import FormSection from '@/components/ui/FormSection';
import FormInput from '@/components/ui/FormInput';
import Btn from '@/components/ui/Btn';
import { tripService, TripStatus } from '@/services/tripService';
import { driverService } from '@/services/driverService';
import { vehicleService } from '@/services/vehicleService';

const STATUS_DESCRIPTIONS: Record<TripStatus, { title: string; description: string; color: string }> = {
  Draft: {
    title: 'Draft (Preparing Shipment)',
    description: 'The trip manifest is being created. Driver and vehicle details can still be attached before dispatch.',
    color: 'bg-slate-50 text-slate-700 border-slate-200',
  },
  Dispatched: {
    title: 'Dispatched (Assigned to Driver)',
    description: 'Driver and truck are assigned and notified. The driver is preparing to head to pickup.',
    color: 'bg-blue-50 text-blue-700 border-blue-200',
  },
  AtPickup: {
    title: 'At Pickup (Loading Dock)',
    description: 'The driver and truck have arrived at the pickup origin point and loading is in progress.',
    color: 'bg-amber-50 text-amber-700 border-amber-200',
  },
  InTransit: {
    title: 'In Transit (On the Road)',
    description: 'Cargo is loaded and the truck is actively driving along the designated shipping route.',
    color: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  },
  AtDelivery: {
    title: 'At Delivery (Unloading Dock)',
    description: 'Truck reached the customer destination and cargo is being inspected and unloaded.',
    color: 'bg-purple-50 text-purple-700 border-purple-200',
  },
  Completed: {
    title: 'Completed (Delivered Successfully)',
    description: 'Shipment delivered, proof of delivery (POD) captured, and trip is ready for settlement.',
    color: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
  Invoiced: {
    title: 'Invoiced (Billed to Client)',
    description: 'Customer invoice generated and attached to commercial accounting records.',
    color: 'bg-cyan-50 text-cyan-700 border-cyan-200',
  },
  Cancelled: {
    title: 'Cancelled (Trip Revoked)',
    description: 'Shipment was cancelled prior to completion due to client request or operational issue.',
    color: 'bg-rose-50 text-rose-700 border-rose-200',
  },
};

export default function EditTripPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [status, setStatus] = useState<TripStatus>('Draft');
  const [selectedDriverId, setSelectedDriverId] = useState<string>('');
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>('');
  const [showHelpGuide, setShowHelpGuide] = useState<boolean>(true);

  // Fetch trip data
  const { data: trip, isLoading, refetch } = useQuery({
    queryKey: ['trip', id],
    queryFn: () => tripService.getById(id!),
    enabled: !!id,
  });

  // Fetch drivers list for reassignment
  const { data: driversRes } = useQuery({
    queryKey: ['drivers-all'],
    queryFn: () => driverService.getAll({ per_page: 100 }),
  });

  // Fetch vehicles list for reassignment
  const { data: vehiclesRes } = useQuery({
    queryKey: ['vehicles-all'],
    queryFn: () => vehicleService.getAll({ per_page: 100 }),
  });

  useEffect(() => {
    if (trip) {
      setStatus(trip.status);
      setSelectedDriverId(trip.driver?.id || '');
      setSelectedVehicleId(trip.vehicle?.id || '');
    }
  }, [trip]);

  // Mutation for status update
  const updateStatusMutation = useMutation({
    mutationFn: (newStatus: TripStatus) => tripService.updateStatus(id!, newStatus),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trip', id] });
      queryClient.invalidateQueries({ queryKey: ['trips'] });
    },
  });

  // Mutation for dispatch / reassignment
  const dispatchMutation = useMutation({
    mutationFn: (payload: { driver_id?: string; vehicle_id?: string }) => tripService.dispatch(id!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trip', id] });
      queryClient.invalidateQueries({ queryKey: ['trips'] });
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      // 1. Update status if changed
      if (trip && status !== trip.status) {
        await updateStatusMutation.mutateAsync(status);
      }

      // 2. Dispatch/reassign driver or vehicle if changed
      const driverChanged = trip?.driver?.id !== selectedDriverId;
      const vehicleChanged = trip?.vehicle?.id !== selectedVehicleId;

      if (driverChanged || vehicleChanged) {
        await dispatchMutation.mutateAsync({
          driver_id: selectedDriverId || undefined,
          vehicle_id: selectedVehicleId || undefined,
        });
      }

      navigate(`/trips/${id}`);
    } catch (err) {
      console.error('Failed to update trip manifest', err);
    }
  };

  if (isLoading || !trip) {
    return (
      <DashboardLayout active="Trips" title="Edit Trip Manifest">
        <div className="p-12 flex flex-col items-center justify-center gap-3">
          <div className="h-8 w-8 border-2 border-[#E8450F] border-t-transparent rounded-full animate-spin"></div>
          <p className="text-xs text-[#6E6E80] font-medium">Loading trip manifest details...</p>
        </div>
      </DashboardLayout>
    );
  }

  const isSubmitting = updateStatusMutation.isPending || dispatchMutation.isPending;
  const currentStatusInfo = STATUS_DESCRIPTIONS[status] || STATUS_DESCRIPTIONS['Draft'];

  return (
    <DashboardLayout 
      active="Trips" 
      title="Edit Trip Manifest" 
      breadcrumb={`Trips / ${trip.ref_id || 'Edit'}`} 
      pageTitle={`Edit Manifest: ${trip.ref_id || 'Draft Trip'}`}
      actions={
        <div className="flex items-center gap-2">
          <Btn 
            label="Refresh" 
            variant="ghost" 
            size="sm" 
            icon={<RefreshCw size={13} />} 
            onClick={() => refetch()} 
          />
          <Btn 
            label="Back to Details" 
            variant="secondary" 
            size="sm" 
            icon={<ArrowLeft size={13} />} 
            onClick={() => navigate(`/trips/${id}`)} 
          />
        </div>
      }
    >
      <div className="mx-auto w-full max-w-4xl px-4 sm:px-6 pb-8 space-y-6 animate-fade-in">
        
        {/* Module Badge & Quick Header Pill */}
        <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-xl border border-black/[0.06] shadow-sm">
          <div className="flex items-center gap-2.5">
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200/80">
              Operations Module
            </span>
            <span className="text-xs text-[#6E6E80] font-medium">
              Cargo: <strong className="text-[#111] font-semibold">{trip.cargo_type || 'General Freight'}</strong>
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowHelpGuide(!showHelpGuide)}
            className="flex items-center gap-1.5 text-xs text-[#E8450F] font-semibold hover:underline"
          >
            <HelpCircle size={14} />
            {showHelpGuide ? 'Hide Help Guide' : 'Why edit a trip manifest?'}
          </button>
        </div>

        {/* Why Edit Trip Manifest Explanation Card */}
        {showHelpGuide && (
          <div className="bg-gradient-to-br from-amber-50/90 via-orange-50/50 to-white rounded-xl p-5 border border-amber-200/80 shadow-sm relative overflow-hidden">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-amber-500/10 text-amber-700 rounded-lg shrink-0 mt-0.5">
                <HelpCircle size={18} />
              </div>
              <div className="space-y-3">
                <div>
                  <h3 className="text-sm font-bold text-amber-950">Why do we edit a Trip Manifest?</h3>
                  <p className="text-xs text-amber-900/80 mt-1 leading-relaxed">
                    A <strong>Trip Manifest</strong> is the live master passport for a shipment. It connects drivers, trucks, shipping status, and routes. Dispatchers edit manifests in plain language to keep fleet logistics smooth and clear:
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div className="flex items-start gap-2 bg-white/80 p-3 rounded-lg border border-amber-200/50">
                    <Truck size={15} className="text-amber-700 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-xs font-bold text-[#111]">1. Reassign Driver or Truck</h4>
                      <p className="text-[11px] text-[#6E6E80]">If a driver falls ill or a truck needs maintenance, swap team members or vehicles instantly.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2 bg-white/80 p-3 rounded-lg border border-amber-200/50">
                    <Clock size={15} className="text-amber-700 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-xs font-bold text-[#111]">2. Update Live Shipment Stage</h4>
                      <p className="text-[11px] text-[#6E6E80]">Advance the status as cargo moves from Pickup → Highway Transit → Customer Delivery.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2 bg-white/80 p-3 rounded-lg border border-amber-200/50">
                    <AlertTriangle size={15} className="text-amber-700 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-xs font-bold text-[#111]">3. Correct Delays & Changes</h4>
                      <p className="text-[11px] text-[#6E6E80]">Adjust schedules when traffic jams, weather, or customer dock delays occur.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2 bg-white/80 p-3 rounded-lg border border-amber-200/50">
                    <ShieldCheck size={15} className="text-amber-700 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-xs font-bold text-[#111]">4. Keep Real-Time Records Clean</h4>
                      <p className="text-[11px] text-[#6E6E80]">Ensure accurate data for customer tracking, legal compliance, and automatic invoicing.</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Main Edit Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          
          {/* Section 1: Update Shipment Status */}
          <FormSection 
            title="1. Update Shipment Progress Stage" 
            description="Select the current real-world status of this shipment so drivers and customers stay synced."
          >
            <div className="space-y-4">
              <FormInput
                label="Current Stage / Status"
                type="select"
                value={status}
                onChange={(e) => setStatus(e.target.value as TripStatus)}
                options={[
                  { value: 'Draft', label: 'Draft — Preparing shipment' },
                  { value: 'Dispatched', label: 'Dispatched — Assigned & notified' },
                  { value: 'AtPickup', label: 'At Pickup — Loading cargo at origin' },
                  { value: 'InTransit', label: 'In Transit — Highway delivery in progress' },
                  { value: 'AtDelivery', label: 'At Delivery — Unloading at customer dock' },
                  { value: 'Completed', label: 'Completed — Delivered & signed off' },
                  { value: 'Invoiced', label: 'Invoiced — Billing processed' },
                  { value: 'Cancelled', label: 'Cancelled — Shipment revoked' },
                ]}
              />

              {/* Status Explanation Highlight Box */}
              <div className={`p-4 rounded-lg border ${currentStatusInfo.color} flex items-start gap-3 transition-colors`}>
                <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-bold">{currentStatusInfo.title}</p>
                  <p className="text-[11px] mt-0.5 opacity-90 leading-relaxed">
                    {currentStatusInfo.description}
                  </p>
                </div>
              </div>
            </div>
          </FormSection>

          {/* Section 2: Assign or Change Driver & Truck */}
          <FormSection 
            title="2. Assign or Change Driver & Truck" 
            description="Reassign team members or vehicles if there are roster changes or maintenance needs."
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              
              {/* Driver Dropdown */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[#111] flex items-center gap-1.5">
                  <UserCheck size={13} className="text-indigo-600" />
                  Assigned Driver
                </label>
                <select
                  value={selectedDriverId}
                  onChange={(e) => setSelectedDriverId(e.target.value)}
                  className="w-full h-10 px-3 rounded-lg border border-black/10 bg-white text-xs font-medium text-[#111] focus:border-[#E8450F] focus:outline-none transition-colors"
                >
                  <option value="">-- No driver assigned (Assign Later) --</option>
                  {driversRes?.data?.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.first_name} {d.last_name} ({d.phone_primary}) — [{d.status}]
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-[#6E6E80]">
                  {selectedDriverId ? 'Driver will receive real-time push alerts on their mobile app.' : 'Select a driver to dispatch this manifest.'}
                </p>
              </div>

              {/* Vehicle Dropdown */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[#111] flex items-center gap-1.5">
                  <Truck size={13} className="text-indigo-600" />
                  Assigned Vehicle / Truck
                </label>
                <select
                  value={selectedVehicleId}
                  onChange={(e) => setSelectedVehicleId(e.target.value)}
                  className="w-full h-10 px-3 rounded-lg border border-black/10 bg-white text-xs font-medium text-[#111] focus:border-[#E8450F] focus:outline-none transition-colors"
                >
                  <option value="">-- No truck assigned (Assign Later) --</option>
                  {vehiclesRes?.data?.map((v) => (
                    <option key={v.id} value={v.id}>
                      Plate: {v.plate_number} ({v.asset_type}) — [{v.status}]
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-[#6E6E80]">
                  {selectedVehicleId ? 'GPS hardware will automatically stream location updates.' : 'Select a vehicle with active GPS telemetry.'}
                </p>
              </div>

            </div>
          </FormSection>

          {/* Bottom Action Bar */}
          <div className="flex items-center justify-between gap-3 pt-4 border-t border-black/[0.06]">
            <p className="text-xs text-[#6E6E80]">
              Press <kbd className="px-1.5 py-0.5 bg-black/5 rounded text-[10px] font-mono">Ctrl + Enter</kbd> to save changes quickly.
            </p>
            <div className="flex gap-3">
              <Btn 
                label="Cancel" 
                variant="secondary" 
                type="button" 
                onClick={() => navigate(`/trips/${id}`)} 
                shortcut={{ key: 'Escape' }}
              />
              <Btn 
                label={isSubmitting ? 'Saving Manifest...' : 'Save Manifest Changes'} 
                type="submit" 
                icon={<Save size={14} />}
                disabled={isSubmitting}
                shortcut={{ key: 'Enter', metaOrControl: true }}
              />
            </div>
          </div>

        </form>
      </div>
    </DashboardLayout>
  );
}
