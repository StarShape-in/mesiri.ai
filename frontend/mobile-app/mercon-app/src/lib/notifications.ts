/**
 * Driver notifications — talks to the mobile notification endpoints.
 *   GET  /mobile/notifications        → the driver's recent notifications
 *   POST /mobile/notifications/:id/read → mark one as read
 */
import { TriangleAlert, Truck, FileText, Settings, Bell, type LucideIcon } from 'lucide-react-native';
import { api } from './api';

export interface MobileNotification {
  id: string;
  title: string;
  message: string;
  type: string; // "Emergency" | "Trip" | "Document" | "System"
  is_read: boolean;
  entity_type?: string | null;
  entity_id?: string | null;
  createdAt: string;
}

export const notificationService = {
  async list(): Promise<MobileNotification[]> {
    const { data } = await api.get('/mobile/notifications');
    return (data.data ?? []) as MobileNotification[];
  },

  async markRead(id: string): Promise<void> {
    await api.post(`/mobile/notifications/${id}/read`);
  },
};

/** lucide icon component for a notification type. */
export function notificationIcon(type: string): LucideIcon {
  switch (type.toLowerCase()) {
    case 'emergency': return TriangleAlert;
    case 'trip': return Truck;
    case 'document': return FileText;
    case 'system': return Settings;
    default: return Bell;
  }
}

/** Relative "time ago" label from an ISO timestamp. */
export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (secs < 60) return 'Just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  const days = Math.floor(hrs / 24);
  return days === 1 ? 'Yesterday' : `${days} days ago`;
}
