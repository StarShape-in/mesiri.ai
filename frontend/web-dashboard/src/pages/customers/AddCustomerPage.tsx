import { useState, useEffect, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  RotateCcw, 
  Plus, 
  CheckCircle2, 
  Circle, 
  Keyboard, 
  ChevronRight, 
  ChevronLeft, 
  Building2, 
  Phone, 
  Mail, 
  DollarSign, 
  Factory, 
  ToggleRight,
  CreditCard,
  Calendar,
  FileCheck,
  Sparkles
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import { customerService, CreateCustomerPayload } from '@/services/customerService';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import Btn from '@/components/ui/Btn';

export default function AddCustomerPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'company' | 'financial'>('company');
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    contact_phone: '',
    email: '',
    industry: '',
    credit_limit: '',
    billing_cycle: '',
    payment_terms: '',
    isActive: true,
  });

  const handleChange = (field: string, value: string | boolean) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleReset = () => {
    setActiveTab('company');
    setFormData({
      name: '',
      contact_phone: '',
      email: '',
      industry: '',
      credit_limit: '',
      billing_cycle: '',
      payment_terms: '',
      isActive: true,
    });
    setError(null);
  };

  // Create Customer Mutation
  const createMutation = useMutation({
    mutationFn: (payload: CreateCustomerPayload) => customerService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      navigate('/customers');
    },
    onError: (err: any) => {
      setError(err.response?.data?.error?.message || err.message || 'Failed to onboard customer');
    },
  });

  const isFormValid = formData.name.trim() !== '' && formData.contact_phone.trim() !== '';

  const handleSubmit = useCallback(() => {
    setError(null);

    if (!formData.name.trim()) {
      setActiveTab('company');
      setError('Company name is required');
      return;
    }
    if (!formData.contact_phone.trim()) {
      setActiveTab('company');
      setError('Primary contact phone is required');
      return;
    }

    createMutation.mutate({
      name: formData.name.trim(),
      contact_phone: formData.contact_phone.trim(),
      credit_limit: formData.credit_limit ? Number(formData.credit_limit) : 0,
    });
  }, [formData, createMutation]);

  // Tab Navigation
  const goToNextTab = useCallback(() => setActiveTab('financial'), []);
  const goToPrevTab = useCallback(() => setActiveTab('company'), []);

  // Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT';

      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        if (isFormValid && !createMutation.isPending) handleSubmit();
        return;
      }
      if (e.altKey && e.key === '1') { e.preventDefault(); setActiveTab('company'); return; }
      if (e.altKey && e.key === '2') { e.preventDefault(); setActiveTab('financial'); return; }
      if ((e.altKey || e.ctrlKey) && e.key === 'ArrowRight') { e.preventDefault(); goToNextTab(); return; }
      if ((e.altKey || e.ctrlKey) && e.key === 'ArrowLeft') { e.preventDefault(); goToPrevTab(); return; }
      if (!isInput) {
        if (e.key === 'ArrowRight') { e.preventDefault(); goToNextTab(); }
        else if (e.key === 'ArrowLeft') { e.preventDefault(); goToPrevTab(); }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [goToNextTab, goToPrevTab, handleSubmit, isFormValid, createMutation.isPending]);

  // Form Completion Tracking
  const completionFields = [
    { label: 'Company Name', filled: formData.name.trim() !== '' },
    { label: 'Contact Phone', filled: formData.contact_phone.trim() !== '' },
    { label: 'Business Email', filled: formData.email.trim() !== '' },
    { label: 'Industry Vertical', filled: formData.industry !== '' },
    { label: 'Credit Limit', filled: formData.credit_limit !== '' },
    { label: 'Billing Cycle', filled: formData.billing_cycle !== '' },
  ];
  const filledCount = completionFields.filter(f => f.filled).length;
  const completionPct = Math.round((filledCount / completionFields.length) * 100);

  // Industry Presets
  const industryPresets = ['Logistics', 'Retail', 'Manufacturing', 'FMCG', 'Government', 'Healthcare', 'Oil & Gas', 'Construction'];

  return (
    <DashboardLayout active="Customers" title="Onboard Customer">
      <div className="px-4 sm:px-6 pb-6 space-y-4 animate-fade-in max-w-[1400px] mx-auto">
        
        {/* Top Scope & Action Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-1 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700">
              <Building2 className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
              <span>MERCON Commercial</span>
              <span>•</span>
              <span className="text-slate-900 dark:text-slate-100 font-bold">Customer Onboarding</span>
            </div>
            <Badge variant="outline" className="bg-cyan-50 text-cyan-700 border-cyan-200 font-bold dark:bg-cyan-950/40 dark:text-cyan-300">
              New Customer
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Btn 
              variant="outline" 
              size="sm" 
              onClick={() => navigate('/customers')}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
              label="Back to Customers"
              icon={<ArrowLeft className="w-3.5 h-3.5" />}
              shortcut={{ key: 'b', alt: true }}
            />
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleReset}
              className="h-9 gap-1.5 text-xs text-slate-500 hover:text-slate-900"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Reset
            </Button>
            <Btn 
              size="sm" 
              onClick={() => handleSubmit()}
              disabled={createMutation.isPending || !isFormValid}
              className="h-9 gap-1.5 text-xs bg-[#E8450F] hover:bg-[#d03d0c] text-white font-bold shadow-xs rounded-md px-4"
              label={createMutation.isPending ? 'Saving...' : 'Onboard Customer'}
              icon={<Plus className="w-3.5 h-3.5" />}
              shortcut={{ key: 'Enter', metaOrControl: true }}
            />
          </div>
        </div>

        <Card className="border border-slate-200 dark:border-slate-800 shadow-2xs rounded-xl overflow-hidden bg-white dark:bg-slate-900">
          <div className="flex flex-col md:flex-row items-center divide-y md:divide-y-0 md:divide-x divide-slate-100 dark:divide-slate-800">
            <div className="flex-1 p-4 flex items-center gap-3 w-full">
              <div className="w-10 h-10 rounded-full flex items-center justify-center bg-cyan-100 text-cyan-600 dark:bg-cyan-900/40 dark:text-cyan-400 shrink-0">
                <Building2 className="w-4.5 h-4.5" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400">Client Account</span>
                <p className="text-sm font-bold truncate mt-0.5 text-slate-900 dark:text-slate-100">
                  {formData.name.trim() || 'New Customer Account'}
                </p>
              </div>
              {formData.name.trim() && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
            </div>
            <div className="flex-1 p-4 flex items-center gap-3 w-full">
              <div className="w-10 h-10 rounded-full flex items-center justify-center bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400 shrink-0">
                <Phone className="w-4.5 h-4.5" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400">Contact Details</span>
                <p className="text-sm font-bold truncate mt-0.5 text-slate-900 dark:text-slate-100 font-mono">
                  {formData.contact_phone.trim() || formData.email.trim() ? `${formData.contact_phone.trim() || 'No Phone'} • ${formData.email.trim() || 'No Email'}` : 'Not Specified'}
                </p>
              </div>
              {(formData.contact_phone.trim() || formData.email.trim()) && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
            </div>
            <div className="flex-1 p-4 flex items-center gap-3 w-full">
              <div className="w-10 h-10 rounded-full flex items-center justify-center bg-amber-100 text-[#E8450F] dark:bg-amber-900/40 dark:text-[#ff6a38] shrink-0">
                <DollarSign className="w-4.5 h-4.5" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400">Financial SLA</span>
                <p className="text-sm font-bold truncate mt-0.5 text-slate-900 dark:text-slate-100 font-mono">
                  Credit Limit: SAR {formData.credit_limit ? Number(formData.credit_limit).toLocaleString() : '0'}
                </p>
              </div>
              {formData.credit_limit && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
            </div>
          </div>
        </Card>

        <div className="max-w-4xl mx-auto w-full pt-2">
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs overflow-hidden">
            <CardHeader className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Building2 className="w-5 h-5 text-orange-500 dark:text-orange-400" />
                  <div>
                    <CardTitle className="text-sm font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      Customer Registration Details
                    </CardTitle>
                    <CardDescription className="text-xs text-slate-500">
                      Configure company identity, contacts, and financial setup.
                    </CardDescription>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-5">
              <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'company' | 'financial')}>
                <TabsList className="grid grid-cols-2 w-full mb-4 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
                  <TabsTrigger value="company" className="text-xs font-semibold flex items-center justify-between gap-1">
                    <span>1. Company Identity</span>
                    <kbd className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded border border-slate-200 dark:border-slate-700 shadow-2xs">Alt+1</kbd>
                  </TabsTrigger>
                  <TabsTrigger value="financial" className="text-xs font-semibold flex items-center justify-between gap-1">
                    <span>2. Financial & Invoicing</span>
                    <kbd className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded border border-slate-200 dark:border-slate-700 shadow-2xs">Alt+2</kbd>
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="company" className="space-y-4 m-0">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5 sm:col-span-2">
                      <Label htmlFor="name" className="text-xs font-semibold text-slate-700 dark:text-slate-300">Company Name / Legal Entity <span className="text-rose-500">*</span></Label>
                      <Input id="name" placeholder="e.g. SABIC Industries Ltd" value={formData.name} onChange={(e) => handleChange('name', e.target.value)} className="h-9 text-xs font-medium border-slate-200" />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="contact_phone" className="text-xs font-semibold text-slate-700 dark:text-slate-300">Primary Contact Phone <span className="text-rose-500">*</span></Label>
                      <div className="relative">
                        <span className="absolute left-3 top-2 text-xs font-bold text-slate-400 font-mono">+966</span>
                        <Input id="contact_phone" placeholder="50XXXXXXX" value={formData.contact_phone} onChange={(e) => handleChange('contact_phone', e.target.value)} className="h-9 text-xs pl-14 font-mono border-slate-200" />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="email" className="text-xs font-semibold text-slate-700 dark:text-slate-300">Billing Email Address <span className="text-rose-500">*</span></Label>
                      <Input id="email" type="email" placeholder="billing@company.com" value={formData.email} onChange={(e) => handleChange('email', e.target.value)} className="h-9 text-xs border-slate-200" />
                    </div>
                  </div>
                  <div className="flex justify-end pt-2">
                    <Btn type="button" size="sm" onClick={goToNextTab} className="text-xs font-bold gap-1 bg-[#E8450F] hover:bg-[#d03d0c] text-white" label="Next: Financial Setup" icon={<ChevronRight className="w-3.5 h-3.5" />} shortcut={{ key: 'ArrowRight', alt: true }} />
                  </div>
                </TabsContent>

                <TabsContent value="financial" className="space-y-4 m-0">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="credit_limit" className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                        <DollarSign className="w-3.5 h-3.5 text-slate-400" /> Credit Limit (SAR)
                      </Label>
                      <Input id="credit_limit" type="number" placeholder="50,000" value={formData.credit_limit} onChange={(e) => handleChange('credit_limit', e.target.value)} className="h-9 text-xs font-medium border-slate-200" />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="billing_cycle" className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-400" /> Billing Cycle
                      </Label>
                      <Select value={formData.billing_cycle} onValueChange={(v) => handleChange('billing_cycle', v)}>
                        <SelectTrigger className="h-9 text-xs font-medium border-slate-200"><SelectValue placeholder="Select billing cycle" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Monthly" className="text-xs">Monthly</SelectItem>
                          <SelectItem value="Quarterly" className="text-xs">Quarterly</SelectItem>
                          <SelectItem value="Annual" className="text-xs">Annual</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="payment_terms" className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                        <CreditCard className="w-3.5 h-3.5 text-slate-400" /> Payment Terms
                      </Label>
                      <Select value={formData.payment_terms} onValueChange={(v) => handleChange('payment_terms', v)}>
                        <SelectTrigger className="h-9 text-xs font-medium border-slate-200"><SelectValue placeholder="Select payment terms" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Net 15" className="text-xs font-mono">Net 15 Days</SelectItem>
                          <SelectItem value="Net 30" className="text-xs font-mono">Net 30 Days (Standard)</SelectItem>
                          <SelectItem value="Net 45" className="text-xs font-mono">Net 45 Days</SelectItem>
                          <SelectItem value="Net 60" className="text-xs font-mono">Net 60 Days</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                        <ToggleRight className="w-3.5 h-3.5 text-slate-400" /> Active Account Status
                      </Label>
                      <div className="flex items-center gap-3 pt-2">
                        <button type="button" onClick={() => setFormData(prev => ({ ...prev, isActive: true }))} className={`text-xs px-3 py-1.5 rounded-lg border font-semibold transition-all ${formData.isActive ? 'bg-emerald-600 text-white border-emerald-600 shadow-2xs font-bold' : 'bg-slate-50 dark:bg-slate-800 text-slate-500 border-slate-200 dark:border-slate-700'}`}>Active</button>
                        <button type="button" onClick={() => setFormData(prev => ({ ...prev, isActive: false }))} className={`text-xs px-3 py-1.5 rounded-lg border font-semibold transition-all ${!formData.isActive ? 'bg-rose-600 text-white border-rose-600 shadow-2xs font-bold' : 'bg-slate-50 dark:bg-slate-800 text-slate-500 border-slate-200 dark:border-slate-700'}`}>Inactive</button>
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
                    <Btn type="button" variant="outline" size="sm" onClick={goToPrevTab} className="text-xs font-bold gap-1 animate-none shadow-none" label="Company Identity" icon={<ChevronLeft className="w-3.5 h-3.5" />} shortcut={{ key: 'ArrowLeft', alt: true }} />
                    <Btn size="sm" onClick={() => handleSubmit()} disabled={createMutation.isPending || !isFormValid} className="text-xs bg-[#E8450F] hover:bg-[#d03d0c] text-white font-bold gap-1 px-4" label={createMutation.isPending ? 'Saving...' : 'Onboard Customer'} icon={<Plus className="w-3.5 h-3.5" />} shortcut={{ key: 'Enter', metaOrControl: true }} />
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
          {error && (
            <div className="p-3 bg-rose-50 text-rose-700 rounded-xl text-xs font-semibold border border-rose-200 flex items-center gap-2 mt-4">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse shrink-0" />
              {error}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
