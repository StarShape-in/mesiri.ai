import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Save, ArrowLeft } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import FormSection from '@/components/ui/FormSection';
import FormInput from '@/components/ui/FormInput';
import Btn from '@/components/ui/Btn';
import { useMutation, useQuery } from '@tanstack/react-query';
import { rateCardService } from '@/services/rateCardService';
import { customerService } from '@/services/customerService';

export default function EditRateCardPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    customerId: '',
    route_origin: '',
    route_destination: '',
    base_price: '',
    currency: 'SAR',
    is_active: true,
  });
  const [error, setError] = useState<string | null>(null);

  // Fetch rate card details
  const { data: rateCard, isLoading: isFetching } = useQuery({
    queryKey: ['rate-card', id],
    queryFn: () => rateCardService.getById(id!),
    enabled: !!id,
  });

  // Sync with form
  useEffect(() => {
    if (rateCard) {
      setFormData({
        name: rateCard.name || '',
        customerId: rateCard.customerId || '',
        route_origin: rateCard.route_origin || '',
        route_destination: rateCard.route_destination || '',
        base_price: rateCard.base_price?.toString() || '',
        currency: rateCard.currency || 'SAR',
        is_active: rateCard.is_active,
      });
    }
  }, [rateCard]);

  // Fetch active customers
  const { data: customersResponse } = useQuery({
    queryKey: ['customers', 'Active'],
    queryFn: () => customerService.getAll({ is_active: true })
  });
  const customers = customersResponse?.data || [];

  const updateMutation = useMutation({
    mutationFn: (data: any) => rateCardService.update(id!, data),
    onSuccess: () => {
      navigate('/rate-cards');
    },
    onError: (err: any) => {
      setError(err.response?.data?.error?.message || err.message || 'Failed to update rate card');
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    updateMutation.mutate({
      name: formData.name,
      customerId: formData.customerId,
      route_origin: formData.route_origin,
      route_destination: formData.route_destination,
      base_price: parseFloat(formData.base_price),
      currency: formData.currency,
      is_active: formData.is_active,
    });
  };

  const handleChange = (field: string, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <DashboardLayout 
      active="Customers" 
      title={`Edit Rate Card: ${id}`}
      breadcrumb="Rate Cards"
      pageTitle={`Edit Rate Card: ${id}`} 
      actions={
        <div className="flex gap-2">
          <Btn label="Cancel" variant="ghost" onClick={() => navigate('/rate-cards')} disabled={updateMutation.isPending} shortcut={{ key: 'Escape' }} />
          <Btn label="Save Changes" icon={<Save size={14} />} onClick={handleSubmit} isLoading={updateMutation.isPending} shortcut={{ key: 'Enter', metaOrControl: true }} />
        </div>
      }
    >
      <div className="mx-auto w-full max-w-4xl px-6 pb-6">
        <button
          onClick={() => navigate('/rate-cards')}
          className="flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft size={16} /> Back to Rate Cards
        </button>

        {isFetching ? (
          <div className="py-20 flex justify-center"><div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></div></div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <FormSection title="General Details" description="Assign this rate card to a specific customer and name the agreement.">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <FormInput
                  label="Rate Card Name"
                  placeholder="e.g. SABIC Dammam Route 2024"
                  value={formData.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  required
                />
                <FormInput
                  label="Customer / Client"
                  type="select"
                  value={formData.customerId}
                  onChange={(e) => handleChange('customerId', e.target.value)}
                  required
                  options={customers.map(c => ({ value: c.id, label: c.name }))}
                />
              </div>
            </FormSection>

            <FormSection title="Route & Pricing" description="Define the origin, destination, and fixed price.">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <FormInput
                  label="Route Origin"
                  placeholder="e.g. Riyadh"
                  value={formData.route_origin}
                  onChange={(e) => handleChange('route_origin', e.target.value)}
                  required
                />
                <FormInput
                  label="Route Destination"
                  placeholder="e.g. Dammam"
                  value={formData.route_destination}
                  onChange={(e) => handleChange('route_destination', e.target.value)}
                  required
                />
                <FormInput
                  label="Base Price"
                  type="number"
                  step="0.01"
                  placeholder="e.g. 1500.00"
                  value={formData.base_price}
                  onChange={(e) => handleChange('base_price', e.target.value)}
                  required
                />
                <FormInput
                  label="Currency"
                  type="select"
                  value={formData.currency}
                  onChange={(e) => handleChange('currency', e.target.value)}
                  required
                  options={[
                    { value: 'SAR', label: 'SAR (Saudi Riyal)' },
                    { value: 'USD', label: 'USD (US Dollar)' },
                  ]}
                />
              </div>
            </FormSection>

            <FormSection title="Status" description="Activate or deactivate this rate card.">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleChange('is_active', !formData.is_active)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${formData.is_active ? 'bg-primary' : 'bg-muted'}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${formData.is_active ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
                <span className="text-sm font-semibold text-foreground">{formData.is_active ? 'Active' : 'Inactive'}</span>
              </div>
            </FormSection>

            {error && (
              <div className="p-4 bg-destructive/10 text-destructive rounded-lg text-sm font-semibold border border-destructive/20">
                {error}
              </div>
            )}

            <div className="bg-[#FEF9C3] border border-[#CA8A04]/20 rounded-lg p-5 shadow-sm">
              <h3 className="text-sm font-bold text-[#CA8A04] mb-1">Pricing Example Preview</h3>
              <p className="text-xs text-[#CA8A04]/80 mb-3">This route will cost exactly:</p>
              <div className="text-2xl font-bold text-[#CA8A04]">
                {formData.currency} {parseFloat(formData.base_price || '0').toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
          </form>
        )}

      </div>
    </DashboardLayout>
  );
}
