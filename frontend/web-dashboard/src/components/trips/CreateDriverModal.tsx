import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { User, Phone, FileText, Calendar, Plus, AlertCircle, Loader2 } from 'lucide-react';

import { driverService, CreateDriverPayload, Driver } from '@/services/driverService';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';

interface CreateDriverModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (driver: Driver) => void;
}

export default function CreateDriverModal({ isOpen, onClose, onCreated }: CreateDriverModalProps) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<CreateDriverPayload>({
    first_name: '',
    last_name: '',
    phone_primary: '',
    license_number: '',
    license_expiry: '',
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({
        first_name: '',
        last_name: '',
        phone_primary: '',
        license_number: '',
        license_expiry: '',
      });
      setError(null);
    }
  }, [isOpen]);

  const createMutation = useMutation({
    mutationFn: (payload: CreateDriverPayload) => driverService.create(payload),
    onSuccess: (newDriver) => {
      queryClient.invalidateQueries({ queryKey: ['drivers'] });
      queryClient.invalidateQueries({ queryKey: ['drivers-select'] });
      onCreated(newDriver);
      onClose();
    },
    onError: (err: any) => {
      setError(err.response?.data?.error?.message || err.message || 'Failed to create driver');
    },
  });

  const handleChange = (field: keyof CreateDriverPayload, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.first_name.trim()) {
      setError('First name is required.');
      return;
    }
    if (!formData.last_name.trim()) {
      setError('Last name is required.');
      return;
    }
    if (!formData.phone_primary.trim()) {
      setError('Primary phone number is required.');
      return;
    }
    if (!formData.license_number.trim()) {
      setError('License number is required.');
      return;
    }
    if (!formData.license_expiry) {
      setError('License expiry date is required.');
      return;
    }
    const isExpiryValid = new Date(formData.license_expiry) > new Date();
    if (!isExpiryValid) {
      setError('License is already expired. Please enter a valid future expiry date.');
      return;
    }

    createMutation.mutate(formData);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[500px] p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl">
        <DialogHeader className="space-y-2 pb-2 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Badge className="bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800 font-semibold px-2.5 py-0.5 text-xs">
              Drivers Module
            </Badge>
          </div>
          <DialogTitle className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <User className="w-5 h-5 text-indigo-600 dark:text-indigo-400" /> Add New Driver
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-500 dark:text-slate-400">
            Create a new driver profile to immediately assign them to this trip.
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
                First Name <span className="text-rose-500">*</span>
              </Label>
              <Input
                placeholder="e.g. John"
                value={formData.first_name}
                onChange={(e) => handleChange('first_name', e.target.value)}
                className="h-9 text-xs border-slate-200 dark:border-slate-800"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Last Name <span className="text-rose-500">*</span>
              </Label>
              <Input
                placeholder="e.g. Doe"
                value={formData.last_name}
                onChange={(e) => handleChange('last_name', e.target.value)}
                className="h-9 text-xs border-slate-200 dark:border-slate-800"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
              <Phone className="w-3.5 h-3.5 text-slate-400" /> Phone Number <span className="text-rose-500">*</span>
            </Label>
            <Input
              placeholder="e.g. +966 50 123 4567"
              value={formData.phone_primary}
              onChange={(e) => handleChange('phone_primary', e.target.value)}
              className="h-9 text-xs border-slate-200 dark:border-slate-800"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <FileText className="w-3.5 h-3.5 text-slate-400" /> Driver License No. <span className="text-rose-500">*</span>
              </Label>
              <Input
                placeholder="e.g. DL-987654"
                value={formData.license_number}
                onChange={(e) => handleChange('license_number', e.target.value)}
                className="h-9 text-xs border-slate-200 dark:border-slate-800 font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-slate-400" /> License Expiry <span className="text-rose-500">*</span>
              </Label>
              <Input
                type="date"
                value={formData.license_expiry}
                onChange={(e) => handleChange('license_expiry', e.target.value)}
                className="h-9 text-xs border-slate-200 dark:border-slate-800"
              />
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
                  Save & Assign Driver
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
