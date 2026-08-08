import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Truck, AlertCircle, Loader2, Plus, Gauge, Cpu } from 'lucide-react';

import { vehicleService, CreateVehiclePayload, Vehicle, AssetType } from '@/services/vehicleService';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface CreateVehicleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (vehicle: Vehicle) => void;
}

export default function CreateVehicleModal({ isOpen, onClose, onCreated }: CreateVehicleModalProps) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<CreateVehiclePayload>({
    plate_number: '',
    asset_type: 'Flatbed',
    capacity_kg: 28000,
    trailer_number: '',
    trailer_type: 'Flatbed',
    trailer_capacity_kg: 28000,
    gps_device_id: '',
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({
        plate_number: '',
        asset_type: 'Flatbed',
        capacity_kg: 28000,
        trailer_number: '',
        trailer_type: 'Flatbed',
        trailer_capacity_kg: 28000,
        gps_device_id: '',
      });
      setError(null);
    }
  }, [isOpen]);

  const createMutation = useMutation({
    mutationFn: (payload: CreateVehiclePayload) => vehicleService.create(payload),
    onSuccess: (newVehicle) => {
      queryClient.invalidateQueries({ queryKey: ['vehicles'] });
      queryClient.invalidateQueries({ queryKey: ['vehicles-select'] });
      onCreated(newVehicle);
      onClose();
    },
    onError: (err: any) => {
      setError(err.response?.data?.error?.message || err.message || 'Failed to create vehicle');
    },
  });

  const handleChange = (field: keyof CreateVehiclePayload, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.plate_number.trim()) {
      setError('Plate number is required.');
      return;
    }
    if (!formData.capacity_kg || formData.capacity_kg <= 0) {
      setError('Valid payload capacity in kg is required.');
      return;
    }

    const payload: CreateVehiclePayload = {
      plate_number: formData.plate_number.trim(),
      asset_type: formData.asset_type,
      capacity_kg: Number(formData.capacity_kg),
      ...(formData.trailer_number?.trim() ? { trailer_number: formData.trailer_number.trim() } : {}),
      ...(formData.trailer_type ? { trailer_type: formData.trailer_type } : {}),
      ...(formData.trailer_capacity_kg ? { trailer_capacity_kg: Number(formData.trailer_capacity_kg) } : {}),
      ...(formData.gps_device_id?.trim() ? { gps_device_id: formData.gps_device_id.trim() } : {}),
    };

    createMutation.mutate(payload);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[520px] p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl">
        <DialogHeader className="space-y-2 pb-2 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Badge className="bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800 font-semibold px-2.5 py-0.5 text-xs">
              Fleet Assets Module
            </Badge>
          </div>
          <DialogTitle className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Truck className="w-5 h-5 text-indigo-600 dark:text-indigo-400" /> Add New Vehicle
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-500 dark:text-slate-400">
            Register a new truck/vehicle in the fleet to immediately assign to this trip.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {error && (
            <div className="p-3 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 rounded-xl text-xs text-rose-600 dark:text-rose-400 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Plate Number <span className="text-rose-500">*</span>
              </Label>
              <Input
                placeholder="e.g. KAA 789X"
                value={formData.plate_number}
                onChange={(e) => handleChange('plate_number', e.target.value)}
                className="h-9 text-xs border-slate-200 dark:border-slate-800 font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Asset Type <span className="text-rose-500">*</span>
              </Label>
              <Select
                value={formData.asset_type}
                onValueChange={(val) => handleChange('asset_type', val as AssetType)}
              >
                <SelectTrigger className="h-9 text-xs border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <SelectValue placeholder="Select type..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Flatbed">Flatbed</SelectItem>
                  <SelectItem value="Reefer">Reefer</SelectItem>
                  <SelectItem value="Box">Box</SelectItem>
                  <SelectItem value="Tanker">Tanker</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <Gauge className="w-3.5 h-3.5 text-slate-400" /> Max Capacity (kg) <span className="text-rose-500">*</span>
              </Label>
              <Input
                type="number"
                placeholder="e.g. 28000"
                value={formData.capacity_kg}
                onChange={(e) => handleChange('capacity_kg', Number(e.target.value))}
                className="h-9 text-xs border-slate-200 dark:border-slate-800"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5 text-slate-400" /> GPS Device ID
              </Label>
              <Input
                placeholder="e.g. GPS-9921"
                value={formData.gps_device_id || ''}
                onChange={(e) => handleChange('gps_device_id', e.target.value)}
                className="h-9 text-xs border-slate-200 dark:border-slate-800 font-mono"
              />
            </div>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200/60 dark:border-slate-800 space-y-2">
            <span className="text-[11px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider block">
              Optional Trailer Details
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-[11px] font-medium text-slate-600 dark:text-slate-400">
                  Trailer Number
                </Label>
                <Input
                  placeholder="e.g. TR-551"
                  value={formData.trailer_number || ''}
                  onChange={(e) => handleChange('trailer_number', e.target.value)}
                  className="h-8 text-xs border-slate-200 dark:border-slate-800 font-mono"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[11px] font-medium text-slate-600 dark:text-slate-400">
                  Trailer Type
                </Label>
                <Select
                  value={formData.trailer_type || 'Flatbed'}
                  onValueChange={(val) => handleChange('trailer_type', val as AssetType)}
                >
                  <SelectTrigger className="h-8 text-xs border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                    <SelectValue placeholder="Trailer type..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Flatbed">Flatbed</SelectItem>
                    <SelectItem value="Reefer">Reefer</SelectItem>
                    <SelectItem value="Box">Box</SelectItem>
                    <SelectItem value="Tanker">Tanker</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <DialogFooter className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={createMutation.isPending}
              className="h-9 text-xs border-slate-200 dark:border-slate-800"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={createMutation.isPending}
              className="h-9 text-xs bg-indigo-600 hover:bg-indigo-700 text-white font-medium gap-1.5 shadow-sm"
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Plus className="w-3.5 h-3.5" />
                  Save & Assign Vehicle
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
