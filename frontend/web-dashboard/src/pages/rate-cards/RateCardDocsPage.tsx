import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { MapPin, Building2, DollarSign, Pencil, ArrowLeft, CalendarDays } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import Btn from '@/components/ui/Btn';
import { rateCardService } from '@/services/rateCardService';

/**
 * Rate cards have no attached documents in the data model, so this route shows
 * the rate card's details instead of a (non-existent) document list.
 */
export default function RateCardDocsPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const { data: card, isLoading, isError } = useQuery({
    queryKey: ['rate-card', id],
    queryFn: () => rateCardService.getById(id!),
    enabled: !!id,
  });

  const Row = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) => (
    <div className="flex items-start gap-3 py-3 border-b border-black/[0.04] last:border-0">
      <div className="w-8 h-8 rounded-lg bg-[#F5F5F7] flex items-center justify-center text-[#6E6E80] shrink-0">{icon}</div>
      <div>
        <p className="text-[10px] uppercase tracking-wider font-bold text-[#9898A4] mb-0.5">{label}</p>
        <p className="text-sm font-semibold text-[#111]">{value}</p>
      </div>
    </div>
  );

  return (
    <DashboardLayout
      active="Rate Cards"
      breadcrumb="Rate Cards"
      title="Rate Card Details"
      pageTitle={card?.name || 'Rate Card'}
      pageSub="Pricing route and rate details."
      actions={
        <div className="flex gap-2">
          <Btn label="Back" variant="ghost" icon={<ArrowLeft size={14} />} onClick={() => navigate('/rate-cards')} />
          {card && <Btn label="Edit" icon={<Pencil size={14} />} onClick={() => navigate(`/rate-cards/${card.id}/edit`)} />}
        </div>
      }
    >
      <div className="px-4 sm:px-6 pb-6 max-w-3xl mx-auto w-full">
        {isLoading ? (
          <div className="p-12 text-center text-sm text-[#9898A4]">Loading…</div>
        ) : isError || !card ? (
          <div className="p-12 text-center text-sm text-[#DC2626]">Rate card not found.</div>
        ) : (
          <div className="bg-white border border-black/[0.08] rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-[#111]">{card.name}</h3>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                card.is_active ? 'bg-[#F0FDF4] text-[#16A34A]' : 'bg-[#F5F5F7] text-[#9898A4]'
              }`}>
                {card.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>

            <Row icon={<MapPin size={16} />} label="Route" value={`${card.route_origin} → ${card.route_destination}`} />
            <Row icon={<DollarSign size={16} />} label="Base Price" value={`${card.currency} ${card.base_price.toLocaleString()}`} />
            <Row icon={<Building2 size={16} />} label="Customer" value={card.customer?.name ?? '—'} />
            <Row icon={<CalendarDays size={16} />} label="Created" value={new Date(card.createdAt).toLocaleDateString()} />
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
