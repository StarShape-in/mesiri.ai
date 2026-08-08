import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  Bell, Check, Clock, AlertTriangle, FileText, Truck, CheckCircle2, 
  RotateCw, Search, ShieldAlert, ArrowRight 
} from 'lucide-react';
import { RiskAlert, CalendarAlert, CheckBadge } from '@/components/ui/kpi-icons';

import DashboardLayout from '@/components/layout/DashboardLayout';
import KpiCard from '@/components/ui/KpiCard';
import { notificationService, type Notification } from '@/services/notificationService';

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

type NotificationType = 'alert' | 'trip' | 'document' | 'system';

/** Backend type strings are free-form ("Emergency"/"Trip"/"system"…) — normalize to 4 buckets. */
function normalizeType(type: string): NotificationType {
  const t = (type || '').toLowerCase();
  if (t.includes('emergency') || t.includes('alert')) return 'alert';
  if (t.includes('trip')) return 'trip';
  if (t.includes('document') || t.includes('doc')) return 'document';
  return 'system';
}

/** Build an in-app link from entity_type + entity_id when present. */
function linkFor(n: Notification): string | undefined {
  if (!n.entity_id || !n.entity_type) return undefined;
  const map: Record<string, string> = { Trip: 'trips', Driver: 'drivers', Vehicle: 'vehicles' };
  const seg = map[n.entity_type];
  return seg ? `/${seg}/${n.entity_id}` : undefined;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const secs = Math.floor((Date.now() - then) / 1000);
  if (secs < 60) return 'Just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins} minute${mins !== 1 ? 's' : ''} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs !== 1 ? 's' : ''} ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days} day${days !== 1 ? 's' : ''} ago`;
  return new Date(iso).toLocaleDateString();
}

export default function NotificationsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'all' | 'unread' | 'alert' | 'trip' | 'document'>('all');
  const [search, setSearch] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data: rawNotifications, isLoading, isError } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const res = await notificationService.getAll();
      const raw = res?.data;
      if (Array.isArray(raw)) return raw;
      if (raw && Array.isArray((raw as any).notifications)) return (raw as any).notifications;
      return [];
    },
  });

  const notifications = useMemo(() => Array.isArray(rawNotifications) ? rawNotifications : [], [rawNotifications]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['notifications'] });
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationService.markAsRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });

  const markAllMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      await Promise.all(ids.map((id) => notificationService.markAsRead(id)));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });

  const unreadCount = notifications.filter((n) => !n.is_read).length;
  const totalCount = notifications.length;
  const readCount = Math.max(0, totalCount - unreadCount);
  const readRatioPct = totalCount > 0 ? Math.round((readCount / totalCount) * 100) : 100;

  const alertCount = notifications.filter(n => normalizeType(n.type) === 'alert').length;
  const tripCount = notifications.filter(n => normalizeType(n.type) === 'trip').length;
  const docCount = notifications.filter(n => normalizeType(n.type) === 'document').length;

  const filteredNotifications = useMemo(() => {
    return notifications.filter((n) => {
      const type = normalizeType(n.type);
      const matchesTab = 
        activeTab === 'all' ? true :
        activeTab === 'unread' ? !n.is_read :
        activeTab === type;

      const q = search.toLowerCase();
      const matchesSearch = 
        (n.title || '').toLowerCase().includes(q) || 
        (n.message || '').toLowerCase().includes(q);

      return matchesTab && matchesSearch;
    });
  }, [notifications, activeTab, search]);

  const markAsRead = (id: string) => {
    if (!markReadMutation.isPending) markReadMutation.mutate(id);
  };

  const markAllAsRead = () => {
    const ids = notifications.filter((n) => !n.is_read).map((n) => n.id);
    if (ids.length) markAllMutation.mutate(ids);
  };

  const getIcon = (type: NotificationType) => {
    switch (type) {
      case 'alert': return <AlertTriangle size={18} className="text-rose-600" />;
      case 'trip': return <Truck size={18} className="text-[#E8450F]" />;
      case 'document': return <FileText size={18} className="text-amber-600" />;
      case 'system': return <Bell size={18} className="text-blue-600" />;
    }
  };

  const getBg = (type: NotificationType) => {
    switch (type) {
      case 'alert': return 'bg-rose-50 border-rose-200';
      case 'trip': return 'bg-orange-50 border-orange-200';
      case 'document': return 'bg-amber-50 border-amber-200';
      case 'system': return 'bg-blue-50 border-blue-200';
    }
  };

  return (
    <DashboardLayout
      active="Dashboard"
      title="Notifications"
    >
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5 max-w-[1400px] mx-auto w-full">
        
        {/* Page Content Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Bell className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />

            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  Notifications Center
                </h1>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={markAllAsRead}
              disabled={unreadCount === 0 || markAllMutation.isPending}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
            >
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
              Mark All as Read
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="h-9 w-9 p-0 text-slate-600 border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
              title="Refresh Data"
            >
              <RotateCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* 4-Card Instrument Panel KPI Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
          
          {/* Card 1: Total Notifications — Gauge */}
          <KpiCard
            title="TOTAL ALERTS LOGGED"
            value={totalCount}
            variant="blue"
            trend="neutral"
            trendValue={`${readRatioPct}% Processed`}
            description="Click to view all notifications"
            icon={CheckBadge}
            completionGauge={{
              percentage: readRatioPct || 100,
              label: `${readRatioPct}% Read & Processed`,
              subtext: `${readCount} Read • ${unreadCount} Unread`
            }}
            onClick={() => setActiveTab('all')}
          />

          {/* Card 2: Unread Alerts — Urgency Bar */}
          <KpiCard
            title="UNREAD NOTIFICATIONS"
            value={unreadCount}
            variant="brand"
            trend={unreadCount > 0 ? 'down' : 'neutral'}
            trendValue={unreadCount > 0 ? 'Pending Read' : 'All Clear'}
            description="Click to view Unread alerts"
            icon={CalendarAlert}
            progressSegments={[
              { label: `${unreadCount} Unread`, value: unreadCount > 0 ? 80 : 0, color: 'bg-[#E8450F]' },
              { label: 'Read', value: unreadCount > 0 ? 20 : 100, color: 'bg-slate-300' },
            ]}
            onClick={() => setActiveTab('unread')}
          />

          {/* Card 3: Emergency Safety Alerts — Urgency Bar */}
          <KpiCard
            title="EMERGENCY SAFETY"
            value={alertCount}
            variant="rose"
            trend={alertCount > 0 ? 'down' : 'neutral'}
            trendValue={alertCount > 0 ? 'Safety Action' : 'Zero Hazards'}
            description="Click for Emergency alerts"
            icon={RiskAlert}
            progressSegments={[
              { label: 'Safety Alerts', value: alertCount > 0 ? 100 : 0, color: 'bg-rose-600' },
            ]}
            onClick={() => setActiveTab('alert')}
          />

          {/* Card 4: Dispatch & Permit Logs — Progress Bar */}
          <KpiCard
            title="DISPATCH & DOCUMENT"
            value={tripCount + docCount}
            variant="emerald"
            trend="neutral"
            trendValue="Automated Logs"
            description="Click for Dispatch updates"
            icon={Truck}
            progressSegments={[
              { label: `Dispatch (${tripCount})`, value: 60, color: 'bg-indigo-600' },
              { label: `Document (${docCount})`, value: 40, color: 'bg-amber-500' },
            ]}
            onClick={() => setActiveTab('trip')}
          />
        </div>

        {/* Toolbar & Filter Bar (Strictly Horizontal) */}
        <div className="bg-white dark:bg-slate-900 rounded-xl p-2.5 shadow-2xs border border-slate-200 dark:border-slate-800 shrink-0">
          <div className="flex items-center justify-between gap-3 overflow-x-auto">
            
            {/* Filter Pills */}
            <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg shrink-0 border border-slate-200/60 dark:border-slate-700">
              <button
                onClick={() => setActiveTab('all')}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all whitespace-nowrap ${
                  activeTab === 'all'
                    ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                All ({totalCount})
              </button>

              <button
                onClick={() => setActiveTab('unread')}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all whitespace-nowrap flex items-center gap-1.5 ${
                  activeTab === 'unread'
                    ? 'bg-white dark:bg-slate-900 text-[#E8450F] shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                <span>Unread</span>
                {unreadCount > 0 && (
                  <Badge className="bg-[#E8450F] text-white text-[9px] px-1.5 py-0 font-bold">
                    {unreadCount}
                  </Badge>
                )}
              </button>

              <button
                onClick={() => setActiveTab('alert')}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all whitespace-nowrap ${
                  activeTab === 'alert'
                    ? 'bg-white dark:bg-slate-900 text-rose-600 shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                Emergency ({alertCount})
              </button>

              <button
                onClick={() => setActiveTab('trip')}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all whitespace-nowrap ${
                  activeTab === 'trip'
                    ? 'bg-white dark:bg-slate-900 text-indigo-600 shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                Dispatch ({tripCount})
              </button>

              <button
                onClick={() => setActiveTab('document')}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all whitespace-nowrap ${
                  activeTab === 'document'
                    ? 'bg-white dark:bg-slate-900 text-amber-600 shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                Documents ({docCount})
              </button>
            </div>

            {/* Search Bar */}
            <div className="relative w-64 shrink-0 ml-auto">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <Input
                type="text"
                placeholder="Search notification title..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-9 text-xs pl-8 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50"
              />
            </div>

          </div>
        </div>

        {/* Notifications Workspace List */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs overflow-hidden shrink-0">
          {isLoading ? (
            <div className="p-12 text-center text-slate-500 text-xs font-medium">Loading notifications...</div>
          ) : isError ? (
            <div className="p-12 text-center text-rose-600 text-xs font-bold">Failed to load notifications.</div>
          ) : filteredNotifications.length === 0 ? (
            <div className="p-12 text-center text-slate-500">
              <CheckCircle2 size={44} className="mx-auto mb-3 text-emerald-500 opacity-60" />
              <p className="text-sm font-extrabold text-slate-900 dark:text-slate-100 mb-1">All Caught Up!</p>
              <p className="text-xs text-slate-500">No new notifications in this view.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {filteredNotifications.map((notif) => {
                const type = normalizeType(notif.type);
                const link = linkFor(notif);
                
                // Class names for type badges
                const badgeClasses: Record<NotificationType, string> = {
                  alert: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/30 dark:text-rose-400 dark:border-rose-800',
                  trip: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/30 dark:text-indigo-400 dark:border-indigo-800',
                  document: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-800',
                  system: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/30 dark:text-blue-400 dark:border-blue-800',
                };

                return (
                  <div
                    key={notif.id}
                    className={cn(
                      "p-4 flex gap-4 transition-all duration-150 ease-in-out hover:bg-slate-100/70 dark:hover:bg-slate-800/80 cursor-pointer outline-none border-l-4",
                      !notif.is_read 
                        ? 'bg-indigo-50/20 dark:bg-indigo-950/15 border-l-[#E8450F]' 
                        : 'bg-white dark:bg-slate-900 border-l-transparent focus-visible:bg-slate-50'
                    )}
                    tabIndex={0}
                    role="button"
                    aria-label={`Notification: ${notif.title}. ${notif.message}`}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        if (!notif.is_read) markAsRead(notif.id);
                        if (link) navigate(link);
                      }
                    }}
                    onClick={() => {
                      if (!notif.is_read) markAsRead(notif.id);
                    }}
                  >
                    <div className={`w-10 h-10 shrink-0 rounded-xl flex items-center justify-center border shadow-3xs ${getBg(type)}`}>
                      {getIcon(type)}
                    </div>

                    <div className="flex-1 pt-0.5">
                      <div className="flex justify-between items-start mb-1 gap-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className={cn(
                            "text-xs tracking-tight",
                            !notif.is_read 
                              ? 'font-extrabold text-slate-950 dark:text-slate-50' 
                              : 'font-semibold text-slate-700 dark:text-slate-300'
                          )}>
                            {notif.title}
                          </h4>
                          <Badge variant="outline" className={cn("text-[9px] font-bold uppercase tracking-wider px-1.5 py-0", badgeClasses[type])}>
                            {type}
                          </Badge>
                        </div>

                        <span className="text-[10px] font-mono font-medium text-slate-400 whitespace-nowrap flex items-center gap-1">
                          <Clock size={11} className="stroke-[2]" /> {relativeTime(notif.createdAt)}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed mb-2.5 pr-6 font-medium">
                        {notif.message}
                      </p>

                      <div className="flex items-center gap-3">
                        {link && (
                          <Button
                            variant="link"
                            size="sm"
                            className="h-auto p-0 text-xs font-bold text-[#E8450F] hover:underline gap-1 focus-visible:ring-1 focus-visible:ring-[#E8450F]"
                            onClick={(e) => { 
                              e.stopPropagation(); 
                              markAsRead(notif.id); 
                              navigate(link);
                            }}
                          >
                            View Entity Details <ArrowRight className="w-3 h-3" />
                          </Button>
                        )}
                        {!notif.is_read && (
                          <button
                            onClick={(e) => { e.stopPropagation(); markAsRead(notif.id); }}
                            className="text-xs font-bold text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 flex items-center gap-1 py-0.5 px-1.5 rounded hover:bg-indigo-50 dark:hover:bg-indigo-950/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/30"
                          >
                            <Check size={12} className="stroke-[2.5]" /> Mark as read
                          </button>
                        )}
                      </div>
                    </div>

                    {!notif.is_read && (
                      <div className="w-2 h-2 rounded-full bg-[#E8450F] shrink-0 mt-2.5 animate-pulse" />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </DashboardLayout>
  );
}
