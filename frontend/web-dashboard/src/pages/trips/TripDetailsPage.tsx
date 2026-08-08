import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, Edit2, Navigation, CheckCircle2, 
  MapPin, Calendar, Clock, Sparkles, ReceiptText, 
  CreditCard, ShieldAlert 
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import StatusBadge from '@/components/ui/StatusBadge';
import Btn from '@/components/ui/Btn';
import ConfirmModal from '@/components/ui/ConfirmModal';
import FormInput from '@/components/ui/FormInput';
import UploadDocumentModal from '@/components/ui/UploadDocumentModal';
import { Combobox } from '@/components/ui/combobox';
import TripLiveMapCard from '@/components/maps/TripLiveMapCard';
import {
  tripService, TripStatus,
  DELAY_REASONS, DELAY_REASON_LABELS, type DelayReason, type TripStop,
} from '@/services/tripService';
import { driverService } from '@/services/driverService';
import { vehicleService } from '@/services/vehicleService';

/** Matches DELAY_THRESHOLD_MINUTES on the server. Below this, lateness is
 *  ordinary variance and showing it would bury the delays that matter. */
const DELAY_THRESHOLD_MINUTES = 30;

/** Minutes a stop was reached late, or null when it isn't late / can't be judged. */
function arrivalDelayMinutes(stop: TripStop): number | null {
  if (!stop.planned_arrival || !stop.actual_arrival) return null;
  const mins = Math.round(
    (new Date(stop.actual_arrival).getTime() - new Date(stop.planned_arrival).getTime()) / 60000,
  );
  return mins >= DELAY_THRESHOLD_MINUTES ? mins : null;
}

function formatDelay(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

export default function TripDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentReason, setPaymentReason] = useState('');
  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  const [nextStatus, setNextStatus] = useState<TripStatus>('Draft');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  // Which stop's reason form is open, and what's typed into it.
  const [delayFormStopId, setDelayFormStopId] = useState<string | null>(null);
  const [delayReason, setDelayReason] = useState<DelayReason>('Traffic');
  const [delayNote, setDelayNote] = useState('');
  const [pendingDriverId, setPendingDriverId] = useState('');
  const [pendingVehicleId, setPendingVehicleId] = useState('');

  // Fetch single trip
  const { data: trip, isLoading } = useQuery({
    queryKey: ['trip', id],
    queryFn: () => tripService.getById(id!),
    enabled: !!id,
  });

  // Available drivers/vehicles for late assignment
  const { data: driversRes } = useQuery({
    queryKey: ['drivers-select', 'Available'],
    queryFn: () => driverService.getAll({ per_page: 100, status: 'Available' }),
    enabled: !!trip && !trip.driver,
  });
  const { data: vehiclesRes } = useQuery({
    queryKey: ['vehicles-select', 'Available'],
    queryFn: () => vehicleService.getAll({ per_page: 100, status: 'Available' }),
    enabled: !!trip && !trip.vehicle,
  });
  const driverOptions = (driversRes?.data || []).map((d) => ({
    value: d.id,
    label: `${d.first_name} ${d.last_name}`,
    keywords: `${d.first_name} ${d.last_name}`,
  }));
  const vehicleOptions = (vehiclesRes?.data || []).map((v) => ({
    value: v.id,
    label: `${v.plate_number} (${v.asset_type} • ${v.capacity_kg.toLocaleString()} kg)`,
    keywords: `${v.plate_number} ${v.asset_type}`,
  }));

  // Assign a driver and/or vehicle to a trip created with "assign later"
  const assignMutation = useMutation({
    mutationFn: (payload: { driver_id?: string; vehicle_id?: string }) => tripService.dispatch(id!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trip', id] });
      queryClient.invalidateQueries({ queryKey: ['trips'] });
      setPendingDriverId('');
      setPendingVehicleId('');
    },
  });

  // Mutate Approve Driver Payment
  const approvePaymentMutation = useMutation({
    mutationFn: (data: { amount: number; reason: string }) => 
      tripService.approvePayment(id!, data.amount, data.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trip', id] });
      setIsPaymentModalOpen(false);
      setPaymentAmount('');
      setPaymentReason('');
    },
  });

  // Record why a stop ran late
  const logDelayMutation = useMutation({
    mutationFn: (vars: { stopId: string; delay_reason: DelayReason; delay_note?: string }) =>
      tripService.logStopDelay(id!, vars.stopId, {
        delay_reason: vars.delay_reason,
        delay_note: vars.delay_note,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trip', id] });
      setDelayFormStopId(null);
      setDelayNote('');
    },
  });

  const openDelayForm = (stop: TripStop) => {
    // Pre-load whatever is already recorded so editing corrects it rather
    // than starting from a blank guess.
    setDelayReason(stop.delay_reason ?? 'Traffic');
    setDelayNote(stop.delay_note ?? '');
    setDelayFormStopId(stop.id);
  };

  // Mutate Trip Status
  const updateStatusMutation = useMutation({
    mutationFn: (status: TripStatus) => tripService.updateStatus(id!, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trip', id] });
      setIsStatusModalOpen(false);
    },
  });

  if (isLoading || !trip) {
    return (
      <DashboardLayout active="Trips" title="Trip Details">
        <div className="p-8 flex items-center justify-center">
          <div className="h-8 w-8 border-2 border-[#E8450F] border-t-transparent rounded-full animate-spin"></div>
        </div>
      </DashboardLayout>
    );
  }

  // Get Next Status Option
  const getNextStatus = (current: TripStatus): TripStatus | null => {
    switch (current) {
      case 'Draft': return 'Dispatched';
      case 'Dispatched': return 'AtPickup';
      case 'AtPickup': return 'InTransit';
      case 'InTransit': return 'AtDelivery';
      case 'AtDelivery': return 'Completed';
      default: return null;
    }
  };

  // A Draft trip can only move to Dispatched once both a driver and a
  // vehicle are assigned — otherwise assign them first via the cards below.
  const rawNextStatus = getNextStatus(trip.status);
  const nextStatusOption =
    rawNextStatus === 'Dispatched' && (!trip.driver || !trip.vehicle) ? null : rawNextStatus;

  return (
    <DashboardLayout 
      active="Trips" 
      title="Trip Details" 
      breadcrumb="Trips" 
      pageTitle={trip.ref_id || 'Trip Details'}
      actions={
        <div className="flex gap-2">
          <Btn 
            label="Back" 
            variant="secondary" 
            size="sm" 
            icon={<ArrowLeft size={13} />} 
            onClick={() => navigate('/trips')} 
          />
          <Btn 
            label="Edit Manifest" 
            variant="secondary" 
            size="sm" 
            icon={<Edit2 size={13} />} 
            onClick={() => navigate(`/trips/${trip.id}/edit`)} 
          />
          {trip.status === 'InTransit' && (
            <Btn 
              label="Track Live" 
              size="sm" 
              icon={<Navigation size={13} />} 
              onClick={() => navigate(`/trips/${trip.id}/track`)} 
            />
          )}
          {nextStatusOption && (
            <Btn 
              label={`Mark ${nextStatusOption}`} 
              size="sm" 
              icon={<CheckCircle2 size={13} />} 
              onClick={() => {
                setNextStatus(nextStatusOption);
                setIsStatusModalOpen(true);
              }} 
            />
          )}
          {trip.status === 'Completed' && (
            <Btn 
              label="Upload POD" 
              size="sm" 
              icon={<ReceiptText size={13} />} 
              onClick={() => setIsUploadModalOpen(true)} 
            />
          )}
        </div>
      }
    >
      <div className="px-4 sm:px-6 pb-6 grid grid-cols-1 lg:grid-cols-3 gap-5 animate-fade-in">
        
        {/* Left Column (Main Trip Content) */}
        <div className="lg:col-span-2 space-y-4">
          
          {/* Trip Summary Card */}
          <div className="bg-[#1C1C2E] rounded-lg p-5 border border-white/5 shadow-lg relative overflow-hidden">
            <div className="flex items-center justify-between mb-5 relative z-10">
              <div>
                <p className="text-[10px] text-white/40 uppercase tracking-widest font-bold">Route Overview</p>
                <p className="text-xl font-bold text-white mt-0.5">{trip.ref_id || 'Draft'}</p>
              </div>
              <StatusBadge status={trip.status} />
            </div>

            {/* Path visualization */}
            <div className="flex items-start gap-4 mt-6 relative z-10">
              <div className="flex flex-col items-center gap-1.5 pt-1">
                <div className="w-3 h-3 rounded-full bg-[#E8450F]" />
                <div className="w-px h-14 bg-white/20" />
                <div className="w-3 h-3 rounded-full bg-[#16A34A]" />
              </div>
              <div className="flex-1 space-y-5">
                <div>
                  <p className="text-[10px] text-white/40 font-bold uppercase tracking-wider">Pickup</p>
                  <p className="text-sm font-bold text-white">Riyadh Industrial Area, Sector 3</p>
                </div>
                <div>
                  <p className="text-[10px] text-white/40 font-bold uppercase tracking-wider">Destination</p>
                  <p className="text-sm font-bold text-white">Jeddah Islamic Port, Terminal 1</p>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-2 text-center max-w-[180px]">
                <div className="px-3 py-2 rounded-lg bg-white/5 border border-white/10">
                  <p className="text-xs font-bold text-white">{trip.planned_distance || 950} km</p>
                  <p className="text-[8px] text-white/40 font-semibold uppercase">Distance</p>
                </div>
                <div className="px-3 py-2 rounded-lg bg-white/5 border border-white/10">
                  <p className="text-xs font-bold text-white">10h 30m</p>
                  <p className="text-[8px] text-white/40 font-semibold uppercase">ETA</p>
                </div>
                <div className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 col-span-2">
                  <p className="text-xs font-bold text-white">{trip.cargo_type}</p>
                  <p className="text-[8px] text-white/40 font-semibold uppercase">Cargo</p>
                </div>
              </div>
            </div>
          </div>

          {/* Live Map Tracking Preview Card */}
          <TripLiveMapCard 
            tripId={trip.id}
            refId={trip.ref_id || 'TRP-8921'}
            pickupLat={trip.stops?.find(s => s.stop_type === 'Pickup')?.location_lat}
            pickupLng={trip.stops?.find(s => s.stop_type === 'Pickup')?.location_lng}
            dropoffLat={trip.stops?.find(s => s.stop_type === 'Dropoff')?.location_lat}
            dropoffLng={trip.stops?.find(s => s.stop_type === 'Dropoff')?.location_lng}
          />

          {/* Stops List */}
          <div className="bg-white rounded-lg p-5 border border-black/[0.06] shadow-sm">
            <h3 className="text-sm font-bold text-[#111] mb-4">Trip Stops Logs</h3>
            <div className="relative border-l border-gray-100 ml-3 space-y-6">
              {(trip.stops || []).map((stop, idx) => (
                <div key={stop.id} className="relative pl-6">
                  <div className={`absolute -left-[7px] top-1.5 w-3.5 h-3.5 rounded-full border-2 border-white flex items-center justify-center ${
                    stop.actual_arrival ? 'bg-[#16A34A]' : 'bg-gray-300'
                  }`} />
                  <div>
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-bold text-[#111]">{stop.stop_type} Stop ({stop.stop_sequence})</p>
                      {stop.actual_arrival && (
                        <span className="text-[9px] font-bold text-[#16A34A] bg-[#F0FDF4] px-1.5 py-0.5 rounded">
                          Checked-in
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-[#6E6E80] mt-0.5">
                      {stop.location_name || `Lat: ${stop.location_lat}, Lng: ${stop.location_lng}`}
                    </p>
                    <div className="flex gap-4 mt-2 text-[10px] text-[#9898A4] font-medium">
                      {stop.planned_arrival && (
                        <span className="flex items-center gap-1"><Calendar size={10} /> Planned: {new Date(stop.planned_arrival).toLocaleString()}</span>
                      )}
                      {stop.actual_arrival && (
                        <span className="flex items-center gap-1 text-[#16A34A]"><Clock size={10} /> Actual: {new Date(stop.actual_arrival).toLocaleString()}</span>
                      )}
                      {stop.actual_departure && (
                        <span className="flex items-center gap-1"><Clock size={10} /> Left: {new Date(stop.actual_departure).toLocaleString()}</span>
                      )}
                    </div>

                    {(() => {
                      const late = arrivalDelayMinutes(stop);
                      if (late === null) return null;
                      const isFormOpen = delayFormStopId === stop.id;

                      return (
                        <div className="mt-2.5 rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
                          <div className="flex items-center justify-between gap-3 flex-wrap">
                            <span className="text-[11px] font-bold text-amber-800">
                              Arrived {formatDelay(late)} late
                            </span>
                            {!isFormOpen && (
                              <button
                                type="button"
                                onClick={() => openDelayForm(stop)}
                                className="text-[10px] font-bold text-amber-900 underline underline-offset-2 hover:text-amber-700"
                              >
                                {stop.delay_reason ? 'Change reason' : 'Add reason'}
                              </button>
                            )}
                          </div>

                          {stop.delay_reason && !isFormOpen && (
                            <p className="text-[11px] text-amber-900 mt-1">
                              {DELAY_REASON_LABELS[stop.delay_reason]}
                              {stop.delay_note ? ` — ${stop.delay_note}` : ''}
                            </p>
                          )}
                          {!stop.delay_reason && !isFormOpen && (
                            <p className="text-[10px] text-amber-700 mt-1">
                              No reason recorded yet.
                            </p>
                          )}

                          {isFormOpen && (
                            <div className="mt-2 space-y-2">
                              <select
                                value={delayReason}
                                onChange={(e) => setDelayReason(e.target.value as DelayReason)}
                                className="w-full h-8 rounded border border-amber-300 bg-white px-2 text-[11px] outline-none focus:border-amber-500"
                              >
                                {DELAY_REASONS.map((r) => (
                                  <option key={r} value={r}>{DELAY_REASON_LABELS[r]}</option>
                                ))}
                              </select>
                              <input
                                type="text"
                                value={delayNote}
                                onChange={(e) => setDelayNote(e.target.value)}
                                maxLength={500}
                                placeholder="Note (optional)"
                                className="w-full h-8 rounded border border-amber-300 bg-white px-2 text-[11px] outline-none focus:border-amber-500"
                              />
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  disabled={logDelayMutation.isPending}
                                  onClick={() => logDelayMutation.mutate({
                                    stopId: stop.id,
                                    delay_reason: delayReason,
                                    delay_note: delayNote.trim() || undefined,
                                  })}
                                  className="h-7 px-3 rounded bg-amber-600 text-white text-[10px] font-bold hover:bg-amber-700 disabled:opacity-50"
                                >
                                  {logDelayMutation.isPending ? 'Saving…' : 'Save reason'}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setDelayFormStopId(null)}
                                  className="h-7 px-3 rounded border border-amber-300 text-amber-900 text-[10px] font-bold hover:bg-amber-100"
                                >
                                  Cancel
                                </button>
                              </div>
                              {logDelayMutation.isError && (
                                <p className="text-[10px] text-red-600">
                                  Could not save that reason. Try again.
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column (Entities & Payment Actions) */}
        <div className="space-y-4">
          
          {/* Driver Card */}
          <div className="bg-white rounded-lg p-5 border border-black/[0.06] shadow-sm">
            <h3 className="text-xs font-bold text-[#9898A4] uppercase tracking-wider mb-3">Assigned Driver</h3>
            {trip.driver ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-[#111]">{trip.driver.first_name} {trip.driver.last_name}</p>
                  <p className="text-xs text-[#6E6E80] mt-0.5">{trip.driver.phone_primary}</p>
                </div>
                <Btn 
                  label="View" 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => navigate(`/drivers/${trip.driver?.id}`)} 
                />
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-[#9898A4]">No driver assigned yet.</p>
                <Combobox
                  value={pendingDriverId}
                  onChange={setPendingDriverId}
                  options={driverOptions}
                  placeholder="Choose available driver..."
                  searchPlaceholder="Search drivers..."
                  emptyText="No available drivers found."
                />
                <Btn
                  label={assignMutation.isPending ? 'Assigning...' : 'Assign Driver'}
                  size="sm"
                  className="w-full"
                  disabled={!pendingDriverId || assignMutation.isPending}
                  onClick={() => assignMutation.mutate({ driver_id: pendingDriverId })}
                />
              </div>
            )}
          </div>

          {/* Vehicle Card */}
          <div className="bg-white rounded-lg p-5 border border-black/[0.06] shadow-sm">
            <h3 className="text-xs font-bold text-[#9898A4] uppercase tracking-wider mb-3">Assigned Vehicle</h3>
            {trip.vehicle ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-[#111]">{trip.vehicle.plate_number}</p>
                  <p className="text-xs text-[#6E6E80] mt-0.5">{trip.vehicle.asset_type} Asset</p>
                </div>
                <Btn
                  label="View"
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate(`/vehicles/${trip.vehicle?.id}`)}
                />
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-[#9898A4]">No vehicle assigned yet.</p>
                <Combobox
                  value={pendingVehicleId}
                  onChange={setPendingVehicleId}
                  options={vehicleOptions}
                  placeholder="Choose available vehicle..."
                  searchPlaceholder="Search vehicles..."
                  emptyText="No available vehicles found."
                />
                <Btn
                  label={assignMutation.isPending ? 'Assigning...' : 'Assign Vehicle'}
                  size="sm"
                  className="w-full"
                  disabled={!pendingVehicleId || assignMutation.isPending}
                  onClick={() => assignMutation.mutate({ vehicle_id: pendingVehicleId })}
                />
              </div>
            )}
          </div>

          {/* Cash Payment Flow */}
          <div className="bg-white rounded-lg p-5 border border-black/[0.06] shadow-sm">
            <h3 className="text-xs font-bold text-[#9898A4] uppercase tracking-wider mb-3">Extra Driver Payment</h3>
            {trip.payment_status === 'Approved' ? (
              <div className="bg-[#F0FDF4] text-[#16A34A] border border-[#16A34A]/10 p-3 rounded-lg">
                <div className="flex items-center justify-between font-bold text-xs">
                  <span>SAR {trip.extra_driver_payment} Approved</span>
                  <CheckCircle2 size={14} />
                </div>
                <p className="text-[10px] text-[#16A34A]/80 mt-1">Reason: {trip.payment_reason}</p>
              </div>
            ) : (
              <div>
                <p className="text-xs text-[#6E6E80] mb-4">Request and approve cash payouts or bonuses for this trip's driver.</p>
                <Btn 
                  label="Approve Cash Payout" 
                  variant="secondary" 
                  icon={<CreditCard size={13} />} 
                  onClick={() => setIsPaymentModalOpen(true)}
                  className="w-full"
                />
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Cash Payout Modal */}
      <ConfirmModal
        isOpen={isPaymentModalOpen}
        onClose={() => setIsPaymentModalOpen(false)}
        title="Approve Driver Cash Payment"
        message="Enter the amount and business reason below to confirm this cashier payout."
        confirmLabel="Approve Payout"
        isDestructive={false}
        isLoading={approvePaymentMutation.isPending}
        onConfirm={() => {
          if (!paymentAmount || !paymentReason) return;
          approvePaymentMutation.mutate({
            amount: parseFloat(paymentAmount),
            reason: paymentReason,
          });
        }}
      >
        <div className="space-y-4 my-4">
          <FormInput
            label="Amount (SAR)"
            type="number"
            required
            placeholder="e.g. 150"
            value={paymentAmount}
            onChange={(e) => setPaymentAmount(e.target.value)}
          />
          <FormInput
            label="Reason"
            type="text"
            required
            placeholder="e.g. Off-loading delay bonus"
            value={paymentReason}
            onChange={(e) => setPaymentReason(e.target.value)}
          />
        </div>
      </ConfirmModal>

      {/* Status Confirmation Modal */}
      <ConfirmModal
        isOpen={isStatusModalOpen}
        onClose={() => setIsStatusModalOpen(false)}
        title={`Update Trip Status`}
        message={`Are you sure you want to transition this trip status to ${nextStatus}?`}
        confirmLabel="Yes, Update"
        isLoading={updateStatusMutation.isPending}
        onConfirm={() => {
          updateStatusMutation.mutate(nextStatus);
        }}
      />

      {/* Upload Document Modal */}
      {trip && (
        <UploadDocumentModal
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
          entityType="Trip"
          entityId={trip.id}
          docType="POD"
          onUploadSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['trip', id] });
            // Show toast or something here optionally
          }}
        />
      )}
    </DashboardLayout>
  );
}
