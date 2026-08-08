import { Check, Clock, AlertTriangle, XCircle } from 'lucide-react';
import { Badge } from './badge';
import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  // Common theme mapping matching s_dashboard status indicators
  const normalized = status.toLowerCase().replace(/\s+/g, '');
  
  // Reference the centralized design tokens (see :root in index.css) rather than
  // hard-coded hex, so status colors stay consistent with the palette.
  let color = 'var(--color-subtle)';
  let bg = 'var(--color-border-soft)';
  let Icon = Clock;

  switch (normalized) {
    case 'available':
    case 'active':
    case 'completed':
    case 'paid':
    case 'verified':
    case 'ontime':
      color = 'var(--color-success)';
      bg = 'var(--color-success-bg)';
      Icon = Check;
      break;
    case 'ontrip':
    case 'intransit':
    case 'dispatched':
    case 'atpickup':
    case 'atdelivery':
    case 'pending':
    case 'pendingreview':
      color = 'var(--color-warning)';
      bg = 'var(--color-warning-bg)';
      Icon = Clock;
      break;
    case 'maintenance':
    case 'offduty':
    case 'draft':
      color = 'var(--color-info)';
      bg = 'var(--color-info-bg)';
      Icon = Clock;
      break;
    case 'overdue':
    case 'expired':
    case 'rejected':
    case 'inactive':
    case 'highrisk':
      color = 'var(--color-error)';
      bg = 'var(--color-error-bg)';
      Icon = AlertTriangle;
      break;
    case 'cancelled':
      color = 'var(--color-purple)';
      bg = 'var(--color-purple-bg)';
      Icon = XCircle;
      break;
  }

  return (
    <Badge 
      variant="outline"
      className={cn("gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full select-none border-transparent")} 
      style={{ color, backgroundColor: bg }}
    >
      <Icon size={12} className="stroke-[2.5]" />
      <span>{status}</span>
    </Badge>
  );
}
