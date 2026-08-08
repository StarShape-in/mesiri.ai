import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { User, Phone, FileText, Calendar, ArrowLeft } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import FormSection from '@/components/ui/FormSection';
import FormInput from '@/components/ui/FormInput';
import Btn from '@/components/ui/Btn';
import { driverService, DriverStatus } from '@/services/driverService';

export default function EditDriverPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: driver, isLoading } = useQuery({
    queryKey: ['driver', id],
    queryFn: () => driverService.getById(id!),
    enabled: !!id,
  });

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    phone_primary: '',
    license_number: '',
    license_expiry: '',
    status: 'Available' as DriverStatus,
  });

  useEffect(() => {
    if (driver) {
      setFormData({
        first_name: driver.first_name,
        last_name: driver.last_name,
        phone_primary: driver.phone_primary,
        license_number: driver.license_number,
        license_expiry: new Date(driver.license_expiry).toISOString().split('T')[0],
        status: driver.status,
      });
    }
  }, [driver]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.license_expiry || Number.isNaN(new Date(formData.license_expiry).getTime())) {
      setError('License Expiry is required and must be a valid date.');
      return;
    }

    setIsSubmitting(true);

    try {
      if (!id) throw new Error('Driver ID missing');
      await driverService.update(id, formData);
      navigate(`/drivers/${id}`);
    } catch (err: any) {
      const details = err.response?.data?.error?.details as { path: string; message: string }[] | undefined;
      const detailMessage = details?.map((d) => `${d.path}: ${d.message}`).join('; ');
      setError(detailMessage || err.response?.data?.error?.message || err.message || 'Failed to update driver');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout active="Drivers" title="Edit Driver">
        <div className="p-6">
          <div className="animate-pulse flex flex-col gap-6">
            <div className="h-64 bg-black/5 rounded-lg"></div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout active="Drivers" title="Edit Driver">
      <div className="mx-auto w-full max-w-4xl px-6 pb-6">
        <button
          onClick={() => navigate('/drivers')}
          className="flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft size={16} /> Back to Drivers
        </button>

        <form onSubmit={handleSubmit} className="space-y-6">
          <FormSection 
            title="Personal Information" 
            description="Basic contact and identification details."
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormInput 
                label="First Name" 
                name="first_name" 
                icon={<User size={16} />} 
                value={formData.first_name}
                onChange={handleChange}
                required
              />
              <FormInput 
                label="Last Name" 
                name="last_name" 
                icon={<User size={16} />} 
                value={formData.last_name}
                onChange={handleChange}
                required
              />
              <FormInput 
                label="Primary Phone" 
                name="phone_primary" 
                icon={<Phone size={16} />} 
                value={formData.phone_primary}
                onChange={handleChange}
                required
              />
              <FormInput
                label="Status"
                type="select"
                name="status"
                value={formData.status}
                onChange={handleChange}
                options={[
                  { value: 'Available', label: 'Available' },
                  { value: 'OnTrip', label: 'On Trip' },
                  { value: 'OffDuty', label: 'Off Duty' },
                  { value: 'Inactive', label: 'Inactive' },
                ]}
              />
            </div>
          </FormSection>

          <FormSection 
            title="Licensing & Compliance" 
            description="Driving license credentials."
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormInput 
                label="License Number" 
                name="license_number" 
                icon={<FileText size={16} />} 
                value={formData.license_number}
                onChange={handleChange}
                required
              />
              <FormInput 
                label="License Expiry" 
                name="license_expiry" 
                type="date"
                icon={<Calendar size={16} />} 
                value={formData.license_expiry}
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
              onClick={() => navigate('/drivers')} 
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
