import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Building2, Phone, DollarSign, ArrowLeft } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import FormSection from '@/components/ui/FormSection';
import FormInput from '@/components/ui/FormInput';
import Btn from '@/components/ui/Btn';
import { customerService } from '@/services/customerService';

export default function EditCustomerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: customer, isLoading } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => customerService.getById(id!),
    enabled: !!id,
  });

  const [formData, setFormData] = useState({
    name: '',
    contact_phone: '',
    credit_limit: '',
    isActive: true,
  });

  useEffect(() => {
    if (customer) {
      setFormData({
        name: customer.name,
        contact_phone: customer.contact_phone,
        credit_limit: customer.credit_limit.toString(),
        isActive: customer.isActive,
      });
    }
  }, [customer]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const value = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value;
    setFormData((prev) => ({ ...prev, [e.target.name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (!id) throw new Error('Customer ID missing');
      
      await customerService.update(id, {
        name: formData.name,
        contact_phone: formData.contact_phone,
        credit_limit: Number(formData.credit_limit),
      });
      navigate(`/customers/${id}`);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || err.message || 'Failed to update customer');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout active="Customers" title="Edit Customer">
        <div className="p-6">
          <div className="animate-pulse flex flex-col gap-6">
            <div className="h-64 bg-black/5 rounded-lg"></div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout active="Customers" title="Edit Customer">
      <div className="mx-auto w-full max-w-4xl px-6 pb-6">
        <button
          onClick={() => navigate('/customers')}
          className="flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft size={16} /> Back to Customers
        </button>

        <form onSubmit={handleSubmit} className="space-y-6">
          <FormSection 
            title="Company Information" 
            description="Basic corporate details and contact information."
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormInput 
                label="Company Name" 
                name="name" 
                icon={<Building2 size={16} />} 
                value={formData.name}
                onChange={handleChange}
                required
              />
              <FormInput 
                label="Contact Phone" 
                name="contact_phone" 
                icon={<Phone size={16} />} 
                value={formData.contact_phone}
                onChange={handleChange}
                required
              />
            </div>
          </FormSection>

          <FormSection 
            title="Financial Setup" 
            description="Credit limits and billing parameters."
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormInput 
                label="Credit Limit (SAR)" 
                name="credit_limit" 
                type="number"
                icon={<DollarSign size={16} />} 
                value={formData.credit_limit}
                onChange={handleChange}
                required
              />
            </div>
          </FormSection>

          {error && (
            <div className="p-4 bg-destructive/10 text-destructive rounded-lg text-sm font-semibold border border-destructive/20">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Btn 
              label="Cancel" 
              variant="outline" 
              type="button" 
              onClick={() => navigate('/customers')} 
              disabled={isSubmitting} 
              shortcut={{ key: 'Escape' }}
            />
            <Btn 
              label={isSubmitting ? 'Saving...' : 'Save Changes'} 
              type="submit" 
              disabled={isSubmitting} 
              shortcut={{ key: 'Enter', metaOrControl: true }}
            />
          </div>
        </form>
      </div>
    </DashboardLayout>
  );
}
