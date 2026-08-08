import { useState, useEffect } from 'react';
import { DollarSign, Clock, PlusCircle, CheckCircle, X } from 'lucide-react';
import { Trip, tripService } from '@/services/tripService';
import Btn from '@/components/ui/Btn';

interface PostTripSettlementModalProps {
  isOpen: boolean;
  onClose: () => void;
  trip: Trip | null;
  onSuccess: () => void;
}

export default function PostTripSettlementModal({
  isOpen,
  onClose,
  trip,
  onSuccess,
}: PostTripSettlementModalProps) {
  const [hasExtraCharges, setHasExtraCharges] = useState<boolean | null>(null);
  const [waitingLabor, setWaitingLabor] = useState<string>('0');
  const [additionalStops, setAdditionalStops] = useState<string>('0');
  const [tripCharges, setTripCharges] = useState<string>('0');
  const [billingAmount, setBillingAmount] = useState<string>('');
  const [carrierName, setCarrierName] = useState<string>('MERCON LOGISTICS');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (trip) {
      setWaitingLabor(trip.waiting_labor_charges ? String(trip.waiting_labor_charges) : '0');
      setAdditionalStops(trip.additional_stop_charges ? String(trip.additional_stop_charges) : '0');
      setTripCharges(trip.trip_charges ? String(trip.trip_charges) : '0');
      setBillingAmount(trip.billing_amount ? String(trip.billing_amount) : '');
      setCarrierName(trip.carrier_name || 'MERCON LOGISTICS');
      setHasExtraCharges(null);
      setError(null);
    }
  }, [trip]);

  if (!isOpen || !trip) return null;

  const handleSubmitNoCharges = async () => {
    setLoading(true);
    setError(null);
    try {
      await tripService.updateFinancials(trip.id, {
        waiting_labor_charges: 0,
        additional_stop_charges: 0,
        is_post_trip_settled: true,
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || 'Failed to complete financial settlement.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitWithCharges = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await tripService.updateFinancials(trip.id, {
        waiting_labor_charges: parseFloat(waitingLabor || '0'),
        additional_stop_charges: parseFloat(additionalStops || '0'),
        trip_charges: parseFloat(tripCharges || '0'),
        billing_amount: billingAmount ? parseFloat(billingAmount) : undefined,
        carrier_name: carrierName,
        is_post_trip_settled: true,
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || 'Failed to update financial charges.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-fade-in">
      <div className="bg-white rounded-2xl border border-black/10 shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-black/[0.06] flex items-center justify-between bg-gray-50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-orange-500/10 text-[#E8450F] flex items-center justify-center">
              <DollarSign size={18} />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#111]">Post-Trip Financial Settlement</h3>
              <p className="text-xs text-[#6E6E80] font-mono">Trip #{trip.ref_id || trip.id.substring(0, 8)}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-200/50 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl font-medium">
              {error}
            </div>
          )}

          {/* Trip Summary Card */}
          <div className="p-3.5 bg-gray-50 rounded-xl border border-black/[0.05] space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-500 font-medium">Customer:</span>
              <span className="font-semibold text-gray-900">{trip.customer?.name || '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500 font-medium">Driver & Vehicle:</span>
              <span className="font-semibold text-gray-900">
                {trip.driver ? `${trip.driver.first_name} ${trip.driver.last_name}` : 'Unassigned'} •{' '}
                {trip.vehicle?.plate_number || 'No Vehicle'}
              </span>
            </div>
          </div>

          {/* Prompt Step */}
          {hasExtraCharges === null ? (
            <div className="space-y-4 text-center py-2">
              <div className="w-12 h-12 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
                <Clock size={24} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-gray-900">Were there any Waiting, Labor, or Extra Charges?</h4>
                <p className="text-xs text-gray-500 mt-1">
                  Confirm if driver recorded detention time, waiting charges, or additional stop costs.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleSubmitNoCharges}
                  disabled={loading}
                  className="py-3 px-4 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 font-semibold text-xs transition-all shadow-xs flex flex-col items-center gap-1"
                >
                  <CheckCircle size={18} className="text-green-600" />
                  <span>No Charges</span>
                  <span className="text-[10px] text-gray-400 font-normal">Complete trip fully (SAR 0 extra)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setHasExtraCharges(true)}
                  className="py-3 px-4 rounded-xl bg-[#E8450F] hover:bg-[#d03d0c] text-white font-semibold text-xs transition-all shadow-xs flex flex-col items-center gap-1"
                >
                  <PlusCircle size={18} />
                  <span>Yes, Enter Charges</span>
                  <span className="text-[10px] text-white/80 font-normal">Add waiting/labor fees</span>
                </button>
              </div>
            </div>
          ) : (
            /* Input Form */
            <form onSubmit={handleSubmitWithCharges} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    Waiting / Labor Charges (SAR)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={waitingLabor}
                    onChange={(e) => setWaitingLabor(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-semibold outline-none focus:border-[#E8450F]"
                    placeholder="0.00"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    Additional Stop Charges (SAR)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={additionalStops}
                    onChange={(e) => setAdditionalStops(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-semibold outline-none focus:border-[#E8450F]"
                    placeholder="0.00"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    Trip Charges / Cost (SAR)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={tripCharges}
                    onChange={(e) => setTripCharges(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-semibold outline-none focus:border-[#E8450F]"
                    placeholder="0.00"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    Base Billing Amount (SAR)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={billingAmount}
                    onChange={(e) => setBillingAmount(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-semibold outline-none focus:border-[#E8450F]"
                    placeholder="Optional base price override"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">
                  Fleet Owner / Subcontractor
                </label>
                <input
                  type="text"
                  value={carrierName}
                  onChange={(e) => setCarrierName(e.target.value)}
                  className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-semibold outline-none focus:border-[#E8450F]"
                  placeholder="MERCON LOGISTICS or 3rd Party"
                />
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setHasExtraCharges(null)}
                  className="text-xs font-semibold text-gray-500 hover:text-gray-800"
                >
                  ← Back
                </button>
                <div className="flex gap-2">
                  <Btn label="Cancel" variant="secondary" onClick={onClose} size="sm" type="button" />
                  <Btn
                    label={loading ? 'Saving...' : 'Save & Complete Trip Settlement'}
                    variant="primary"
                    size="sm"
                    type="submit"
                    disabled={loading}
                  />
                </div>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
