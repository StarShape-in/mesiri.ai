import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  User,
  Phone,
  FileText,
  Calendar,
  ArrowLeft,
  RotateCcw,
  Plus,
  CheckCircle2,
  Circle,
  ShieldCheck,
  Keyboard,
  AlertCircle,
  Building2,
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import { driverService, CreateDriverPayload } from '@/services/driverService';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import Btn from '@/components/ui/Btn';

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  phone_primary: '',
  license_number: '',
  license_expiry: '',
};

export default function AddDriverPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState(EMPTY_FORM);

  const handleChange = (field: keyof typeof EMPTY_FORM, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleReset = () => {
    setFormData(EMPTY_FORM);
    setError(null);
  };

  const createMutation = useMutation({
    mutationFn: (payload: CreateDriverPayload) => driverService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drivers'] });
      queryClient.invalidateQueries({ queryKey: ['fleet-performance'] });
      navigate('/drivers');
    },
    onError: (err: any) => {
      setError(err.response?.data?.error?.message || err.message || 'Failed to create driver');
    },
  });

  const isExpiryValid = formData.license_expiry ? new Date(formData.license_expiry) > new Date() : false;
  const isExpired = formData.license_expiry !== '' && !isExpiryValid;

  const checklist = [
    { label: 'Driver name', value: `${formData.first_name} ${formData.last_name}`.trim(), done: formData.first_name.trim() !== '' && formData.last_name.trim() !== '', icon: User, placeholder: 'First and last name' },
    { label: 'Contact phone', value: formData.phone_primary.trim() && `+966 ${formData.phone_primary.trim()}`, done: formData.phone_primary.trim() !== '', icon: Phone, placeholder: 'Primary number' },
    { label: 'License number', value: formData.license_number.trim(), done: formData.license_number.trim() !== '', icon: FileText, placeholder: 'Saudi license ID' },
    { label: 'License expiry', value: formData.license_expiry, done: isExpiryValid, icon: Calendar, placeholder: 'Future-dated' },
  ];

  const completed = checklist.filter((item) => item.done).length;
  const isFormValid = completed === checklist.length;

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    setError(null);

    if (!formData.first_name.trim()) return setError('First name is required');
    if (!formData.last_name.trim()) return setError('Last name is required');
    if (!formData.phone_primary.trim()) return setError('Primary phone number is required');
    if (!formData.license_number.trim()) return setError('License number is required');
    if (!formData.license_expiry) return setError('License expiry date is required');
    if (!isExpiryValid) {
      return setError('License is already expired. Only drivers with a valid, future-dated license can be onboarded.');
    }

    createMutation.mutate({
      first_name: formData.first_name.trim(),
      last_name: formData.last_name.trim(),
      phone_primary: formData.phone_primary.trim(),
      license_number: formData.license_number.trim(),
      license_expiry: formData.license_expiry,
    });
  };

  const fullName = `${formData.first_name} ${formData.last_name}`.trim();
  const initials = ((formData.first_name[0] || 'D') + (formData.last_name[0] || 'R')).toUpperCase();

  return (
    <DashboardLayout active="Drivers" title="Onboard New Driver">
      <form
        onSubmit={handleSubmit}
        className="mx-auto w-full max-w-6xl px-4 sm:px-6 pb-6 space-y-4 animate-fade-in"
      >
        {/* Scope & actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-md border bg-muted px-2.5 py-1 text-xs font-semibold text-muted-foreground">
              <Building2 className="w-3.5 h-3.5" />
              MERCON Fleet
              <span className="text-muted-foreground/50">/</span>
              <span className="text-foreground font-bold">Human Capital</span>
            </span>
            <Badge variant="outline" className="font-semibold">Driver Onboarding</Badge>
          </div>

          <div className="flex items-center gap-2">
            <Btn
              type="button"
              variant="outline"
              size="sm"
              onClick={() => navigate('/drivers')}
              className="h-9 text-xs"
              label="Back"
              icon={<ArrowLeft className="w-3.5 h-3.5" />}
              shortcut={{ key: 'b', alt: true }}
            />
            <Button type="button" variant="ghost" size="sm" onClick={handleReset} className="h-9 text-xs gap-1.5">
              <RotateCcw className="w-3.5 h-3.5" /> Reset
            </Button>
            <Btn
              type="submit"
              size="sm"
              disabled={createMutation.isPending || !isFormValid}
              className="h-9 px-4 text-xs rounded-md"
              label={createMutation.isPending ? 'Onboarding...' : 'Onboard Driver'}
              icon={<Plus className="w-3.5 h-3.5" />}
              shortcut={{ key: 'Enter', metaOrControl: true }}
            />
          </div>
        </div>

        {/* Workspace: form + live summary side by side */}
        <div className="grid gap-4 lg:grid-cols-3 items-start">
          {/* Form */}
          <Card className="lg:col-span-2 rounded-xl">
            <CardHeader className="border-b">
              <CardTitle className="text-sm font-bold">Driver details</CardTitle>
              <CardDescription className="text-xs">
                Personal contact info and commercial Saudi license credentials.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-5">
              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                  <User className="w-3.5 h-3.5" /> Personal profile
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="first_name" className="text-xs font-semibold">
                      First name <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="first_name"
                      autoFocus
                      placeholder="e.g. Ahmed"
                      value={formData.first_name}
                      onChange={(e) => handleChange('first_name', e.target.value)}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="last_name" className="text-xs font-semibold">
                      Last name <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="last_name"
                      placeholder="e.g. Al-Mansoor"
                      value={formData.last_name}
                      onChange={(e) => handleChange('last_name', e.target.value)}
                    />
                  </div>

                  <div className="space-y-1.5 sm:col-span-2">
                    <Label htmlFor="phone_primary" className="text-xs font-semibold">
                      Primary phone <span className="text-destructive">*</span>
                    </Label>
                    <div className="relative">
                      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 font-mono text-xs font-bold text-muted-foreground">
                        +966
                      </span>
                      <Input
                        id="phone_primary"
                        inputMode="tel"
                        placeholder="50XXXXXXX"
                        value={formData.phone_primary}
                        onChange={(e) => handleChange('phone_primary', e.target.value)}
                        className="pl-14 font-mono"
                      />
                    </div>
                  </div>
                </div>
              </section>

              <Separator />

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                  <ShieldCheck className="w-3.5 h-3.5" /> Commercial driving license
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="license_number" className="text-xs font-semibold">
                      Saudi license ID <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="license_number"
                      placeholder="e.g. 10XXXXXXXX"
                      value={formData.license_number}
                      onChange={(e) => handleChange('license_number', e.target.value)}
                      className="font-mono"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="license_expiry" className="flex items-center justify-between text-xs font-semibold">
                      <span>Expiry date <span className="text-destructive">*</span></span>
                      {formData.license_expiry && (
                        <span
                          className={`rounded-full border px-1.5 py-0.5 text-[10px] font-bold ${
                            isExpiryValid
                              ? 'text-emerald-600 border-emerald-200 bg-emerald-50 dark:bg-emerald-950/40'
                              : 'text-destructive border-destructive/25 bg-destructive/10'
                          }`}
                        >
                          {isExpiryValid ? 'Valid' : 'Expired'}
                        </span>
                      )}
                    </Label>
                    <Input
                      id="license_expiry"
                      type="date"
                      value={formData.license_expiry}
                      onChange={(e) => handleChange('license_expiry', e.target.value)}
                      aria-invalid={isExpired}
                      className={`font-mono ${isExpired ? 'border-destructive' : ''}`}
                    />
                  </div>
                </div>
              </section>

              {error && (
                <Alert variant="destructive">
                  <AlertCircle />
                  <AlertTitle>Cannot onboard this driver</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
            </CardContent>

            <CardFooter className="justify-between rounded-b-xl">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Keyboard className="w-3.5 h-3.5" /> Press Ctrl + Enter to submit
              </span>
              <Button type="button" variant="outline" size="sm" onClick={handleReset} className="h-8 text-xs">
                Reset form
              </Button>
            </CardFooter>
          </Card>

          {/* Live summary */}
          <Card className="rounded-xl lg:sticky lg:top-2">
            <CardHeader className="border-b">
              <CardTitle className="text-sm font-bold">Onboarding summary</CardTitle>
              <CardDescription className="text-xs">
                {completed} of {checklist.length} requirements complete
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                  {initials}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold">{fullName || 'New driver candidate'}</p>
                  <p className="truncate text-xs text-muted-foreground font-mono">
                    {formData.license_number || 'DL-XXXX-XXXX'}
                  </p>
                </div>
              </div>

              <Separator />

              <ul className="space-y-2.5">
                {checklist.map((item) => (
                  <li key={item.label} className="flex items-start gap-2.5">
                    {item.done ? (
                      <CheckCircle2 className="mt-0.5 w-4 h-4 shrink-0 text-emerald-500" />
                    ) : (
                      <Circle className="mt-0.5 w-4 h-4 shrink-0 text-muted-foreground/40" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold">{item.label}</p>
                      <p className={`truncate text-xs ${item.done ? 'text-muted-foreground' : 'text-muted-foreground/60'}`}>
                        {item.value || item.placeholder}
                      </p>
                    </div>
                    <item.icon className="mt-0.5 w-3.5 h-3.5 shrink-0 text-muted-foreground/40" />
                  </li>
                ))}
              </ul>
            </CardContent>

            <CardFooter className="rounded-b-xl">
              <p className="text-xs text-muted-foreground">
                {isFormValid
                  ? 'All checks passed — ready to onboard.'
                  : 'Complete every requirement to enable onboarding.'}
              </p>
            </CardFooter>
          </Card>
        </div>
      </form>
    </DashboardLayout>
  );
}
