import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckSquare, Upload, FileText, CheckCircle2 } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import FormSection from '@/components/ui/FormSection';
import FormInput from '@/components/ui/FormInput';
import Btn from '@/components/ui/Btn';
import { tripService } from '@/services/tripService';
import { documentService } from '@/services/documentService';

export default function TripCompletionPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [remarks, setRemarks] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const { data: trip, isLoading } = useQuery({
    queryKey: ['trip-completion', id],
    queryFn: () => tripService.getById(id!),
    enabled: !!id,
  });

  const completionMutation = useMutation({
    mutationFn: async () => {
      // 1. Upload POD document if selected
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('entity_type', 'Trip');
        formData.append('entity_id', id!);
        formData.append('doc_type', 'POD');
        await documentService.upload(formData);
      }
      // 2. Set Trip Status to Completed
      return tripService.updateStatus(id!, 'Completed');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trip', id] });
      navigate(`/trips/${id}`);
    },
  });

  if (isLoading || !trip) {
    return (
      <DashboardLayout active="Trips" title="Trip Completion">
        <div className="p-8 flex items-center justify-center">
          <div className="h-8 w-8 border-2 border-[#E8450F] border-t-transparent rounded-full animate-spin"></div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout 
      active="Trips" 
      title="Trip Completion" 
      breadcrumb={`Trips / ${trip.ref_id || 'Complete'}`} 
      pageTitle="Complete Shipment Review"
      actions={
        <Btn 
          label="Back" 
          variant="secondary" 
          size="sm" 
          icon={<ArrowLeft size={13} />} 
          onClick={() => navigate(`/trips/${id}`)} 
        />
      }
    >
      <div className="mx-auto w-full max-w-2xl px-6 pb-6 animate-fade-in">
        <div className="bg-card rounded-lg border border-border p-5 shadow-sm mb-5">
          <h3 className="text-sm font-bold text-foreground mb-2">Completion Check</h3>
          <p className="text-xs text-muted-foreground font-medium leading-relaxed">
            Verify the cargo has been safely delivered, upload the client's signed POD (Proof of Delivery) document, and close the shipment.
          </p>
        </div>

        <FormSection title="Proof of Delivery & Closing Notes">
          <div className="col-span-2 flex flex-col gap-1.5">
            <label className="text-xs font-bold text-[#111]">POD File Upload (PDF, PNG, JPG)</label>
            <div className="border-2 border-dashed border-gray-200 rounded-lg p-6 text-center flex flex-col items-center justify-center hover:bg-gray-50 transition-colors cursor-pointer relative">
              <input 
                type="file" 
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <Upload size={24} className="text-gray-400 mb-2 stroke-[1.5]" />
              <p className="text-xs font-bold text-[#111]">
                {file ? file.name : 'Choose signed POD document'}
              </p>
              <p className="text-[10px] text-gray-400 mt-1 font-medium">Max file size 10MB</p>
            </div>
          </div>

          <FormInput
            label="Operator Closing Notes"
            type="textarea"
            span
            placeholder="Add comments on off-loading time, cargo condition or any incident reports..."
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
          />
        </FormSection>

        <div className="flex gap-3">
          <Btn 
            label="Cancel" 
            variant="secondary" 
            type="button" 
            onClick={() => navigate(`/trips/${id}`)} 
          />
          <Btn 
            label="Approve & Complete" 
            icon={<CheckCircle2 size={14} />}
            disabled={completionMutation.isPending}
            onClick={() => completionMutation.mutate()}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}
