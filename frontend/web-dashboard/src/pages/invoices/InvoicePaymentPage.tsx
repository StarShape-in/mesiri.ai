import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { DollarSign, ArrowLeft, CheckCircle, AlertTriangle } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import FormSection from '@/components/ui/FormSection';
import Btn from '@/components/ui/Btn';
import { invoiceService } from '@/services/invoiceService';

export default function InvoicePaymentPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: invoice, isLoading } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => invoiceService.getById(id!),
    enabled: !!id,
  });

  const handleMarkAsPaid = async () => {
    setError(null);
    setIsSubmitting(true);

    try {
      if (!id) return;
      await invoiceService.updateStatus(id, 'Paid');
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoice', id] });
      navigate(`/invoices/${id}`);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || err.message || 'Failed to update invoice status');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout active="Invoices" title="Record Payment">
        <div className="p-6">
          <div className="animate-pulse h-64 bg-black/5 rounded-lg"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (!invoice) return null;

  return (
    <DashboardLayout active="Invoices" title="Record Payment">
      <div className="px-4 sm:px-6 pb-6 max-w-3xl">
        <button 
          onClick={() => navigate('/invoices')}
          className="flex items-center gap-2 text-sm font-semibold text-[#6E6E80] hover:text-[#111] transition-colors mb-6"
        >
          <ArrowLeft size={16} /> Back to Invoices
        </button>

        <div className="bg-white border border-black/[0.08] rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-6 pb-6 border-b border-black/[0.04]">
            <div>
              <h2 className="text-xl font-bold text-[#111]">Invoice {invoice.ref_id || invoice.id.split('-')[0].toUpperCase()}</h2>
              <p className="text-sm text-[#6E6E80] mt-1">{invoice.customer?.name}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-[#6E6E80] font-medium">Total Amount Due</p>
              <h3 className="text-2xl font-bold text-[#E8450F]">{invoice.currency} {invoice.total_amount.toLocaleString()}</h3>
            </div>
          </div>

          <div className="bg-green-50 border border-green-100 rounded-lg p-5 mb-6 flex gap-4 items-start">
            <CheckCircle className="text-green-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-green-900 mb-1">Confirm Payment Receipt</h4>
              <p className="text-sm text-green-800">
                Marking this invoice as Paid will update the system ledgers and clear the outstanding balance for {invoice.customer?.name}. This action cannot be undone easily.
              </p>
            </div>
          </div>

          {error && (
            <div className="p-4 bg-red-50 text-red-600 rounded-lg text-sm font-semibold border border-red-100 mb-6 flex items-center gap-2">
              <AlertTriangle size={16} /> {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4">
            <Btn 
              label="Cancel" 
              variant="outline" 
              onClick={() => navigate(`/invoices/${id}`)} 
              disabled={isSubmitting} 
            />
            <Btn 
              label={isSubmitting ? 'Processing...' : 'Mark as Paid'} 
              onClick={handleMarkAsPaid} 
              disabled={isSubmitting || invoice.status === 'Paid'} 
            />
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
