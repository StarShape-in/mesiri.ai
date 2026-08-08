import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { invoiceService } from '@/services/invoiceService';

export default function InvoicePrintTemplate() {
  const { id } = useParams<{ id: string }>();

  const { data: invoice, isLoading, error } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => invoiceService.getById(id!),
    enabled: !!id,
  });

  useEffect(() => {
    if (invoice && !isLoading) {
      // Small delay to ensure styles and fonts are loaded before triggering print
      const timer = setTimeout(() => {
        window.print();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [invoice, isLoading]);

  if (isLoading) {
    return <div className="p-10 text-center font-sans text-gray-500">Loading invoice data...</div>;
  }

  if (error || !invoice) {
    return <div className="p-10 text-center font-sans text-red-500">Invoice not found or error loading data.</div>;
  }

  const invoiceNumber = invoice.ref_id || invoice.id.split('-')[0].toUpperCase();

  return (
    <div className="bg-white min-h-screen font-sans text-[#111]">
      <div className="max-w-4xl mx-auto p-10 bg-white" style={{ width: '210mm', minHeight: '297mm' }}>
        
        {/* Header */}
        <div className="flex justify-between items-start border-b-2 border-[#E8450F] pb-6 mb-8 overflow-visible relative">
          <div className="-ml-16 pt-2">
            <img src="/invoice-logo.png" alt="MERCON Logo" className="h-40 w-auto mb-2 object-contain scale-[1.3] origin-left" />
            <div className="mt-4 text-sm text-gray-600">
              <p>Riyadh, Saudi Arabia</p>
              <p>info@mercon.com</p>
              <p>+966 50 000 0000</p>
            </div>
          </div>
          <div className="text-right">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">INVOICE</h2>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-600 text-right">
              <span className="font-semibold text-gray-900">Invoice No:</span>
              <span>{invoiceNumber}</span>
              <span className="font-semibold text-gray-900">Date:</span>
              <span>{new Date(invoice.createdAt).toLocaleDateString()}</span>
              <span className="font-semibold text-gray-900">Due Date:</span>
              <span className={new Date(invoice.due_date) < new Date() && invoice.status !== 'Paid' ? 'text-red-600 font-bold' : ''}>
                {new Date(invoice.due_date).toLocaleDateString()}
              </span>
            </div>
            <div className="mt-4 inline-block px-3 py-1 rounded border-2 border-gray-900 text-sm font-bold uppercase tracking-widest">
              {invoice.status}
            </div>
          </div>
        </div>

        {/* Billing Info */}
        <div className="flex justify-between items-start mb-12">
          <div>
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Billed To</h3>
            <p className="text-lg font-bold text-gray-900 mb-1">{invoice.customer?.name || 'Unknown Customer'}</p>
            <p className="text-sm text-gray-600">Customer ID: {invoice.customer?.id?.split('-')[0].toUpperCase()}</p>
          </div>
          <div className="text-right">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Trip Reference</h3>
            <p className="text-base font-bold text-gray-900">{invoice.trip?.ref_id || 'N/A'}</p>
          </div>
        </div>

        {/* Line Items */}
        <div className="mb-12">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b-2 border-gray-900">
                <th className="py-3 text-sm font-bold text-gray-900 uppercase">Description</th>
                <th className="py-3 text-sm font-bold text-gray-900 uppercase text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              <tr>
                <td className="py-4 text-sm text-gray-800">
                  Freight Transportation Services (Trip {invoice.trip?.ref_id || 'N/A'})
                </td>
                <td className="py-4 text-sm font-medium text-gray-900 text-right">
                  {invoice.currency} {invoice.subtotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </td>
              </tr>
              {/* Optional extra rows could go here if the backend provided them */}
            </tbody>
          </table>
        </div>

        {/* Totals */}
        <div className="flex justify-end mb-16">
          <div className="w-1/2">
            <div className="flex justify-between py-2 text-sm text-gray-600">
              <span>Subtotal</span>
              <span>{invoice.currency} {invoice.subtotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between py-2 text-sm text-gray-600 border-b border-gray-300">
              <span>Tax (0%)</span>
              <span>{invoice.currency} 0.00</span>
            </div>
            <div className="flex justify-between py-4 text-xl font-bold text-[#E8450F]">
              <span>Total Due</span>
              <span>{invoice.currency} {invoice.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-8 border-t border-gray-200 text-center text-xs text-gray-500">
          <p className="font-semibold text-gray-900 mb-1">Thank you for your business.</p>
          <p>Please make checks payable to MERCON Logistics. Payment is due within 30 days.</p>
        </div>

      </div>
    </div>
  );
}
