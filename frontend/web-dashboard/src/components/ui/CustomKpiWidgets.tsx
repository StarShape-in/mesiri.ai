import * as React from 'react';
import { cn } from '@/lib/utils';
import { Star, ShieldCheck, Truck, User, ArrowRight, AlertTriangle, CheckCircle, Clock } from 'lucide-react';

/**
 * 1. Speedometer Dial Gauge (For /dashboard Fleet Utilization)
 */
export function SpeedometerGaugeKpi({ percentage, label, subtext }: { percentage: number; label: string; subtext?: string }) {
  const clamped = Math.min(100, Math.max(0, percentage));
  const strokeDash = (clamped / 100) * 126; // Arc length for semi-circle (r=20, pi*r ≈ 63)

  return (
    <div className="flex items-center justify-between gap-3 px-1 py-0.5">
      <div className="flex flex-col">
        <span className="text-xs font-extrabold text-indigo-600 dark:text-indigo-400">{label}</span>
        {subtext && <span className="text-[10px] text-slate-500 font-mono mt-0.5">{subtext}</span>}
      </div>

      <div className="relative w-14 h-8 flex items-end justify-center shrink-0">
        <svg className="w-14 h-14 -rotate-90 transform" viewBox="0 0 48 48">
          {/* Background arc */}
          <circle
            cx="24"
            cy="24"
            r="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            className="text-slate-100 dark:text-slate-800"
            strokeDasharray="63 126"
          />
          {/* Active arc */}
          <circle
            cx="24"
            cy="24"
            r="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            strokeLinecap="round"
            className="text-indigo-600 dark:text-indigo-400 transition-all duration-500"
            strokeDasharray={`${strokeDash} 126`}
          />
        </svg>
        <span className="absolute bottom-0 text-[10px] font-extrabold font-mono text-indigo-700 dark:text-indigo-300">
          {clamped}%
        </span>
      </div>
    </div>
  );
}

/**
 * 2. Live Dispatch Telemetry Radar (For /dashboard & /trips)
 */
export function DispatchTelemetryRadarKpi({ activeCount, totalCount, label }: { activeCount: number; totalCount: number; label: string }) {
  const pct = totalCount > 0 ? Math.round((activeCount / totalCount) * 100) : 0;

  return (
    <div className="flex flex-col gap-2 px-1 py-0.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-extrabold text-slate-800 dark:text-slate-200">{label}</span>
        </div>
        <span className="text-[10px] font-mono font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-full border border-emerald-200/80">
          {pct}% Active
        </span>
      </div>

      <div className="w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden flex gap-0.5">
        <div className="bg-emerald-500 h-full rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
        <div className="bg-slate-200 dark:bg-slate-700 h-full rounded-full flex-1" />
      </div>
    </div>
  );
}

/**
 * 3. Driver Photo Avatar Stack & Safety Score (For /drivers)
 */
export function DriverRosterKpi({ count, onlineCount, safetyScore }: { count: number; onlineCount: number; safetyScore?: number }) {
  return (
    <div className="flex items-center justify-between gap-3 px-1 py-0.5">
      {/* Avatar Stack */}
      <div className="flex items-center">
        <div className="flex -space-x-2 overflow-hidden">
          <div className="inline-block h-7 w-7 rounded-full ring-2 ring-white dark:ring-slate-900 bg-indigo-500 text-white flex items-center justify-center text-[10px] font-bold">
            <User className="w-3.5 h-3.5" />
          </div>
          <div className="inline-block h-7 w-7 rounded-full ring-2 ring-white dark:ring-slate-900 bg-emerald-500 text-white flex items-center justify-center text-[10px] font-bold">
            <User className="w-3.5 h-3.5" />
          </div>
          <div className="inline-block h-7 w-7 rounded-full ring-2 ring-white dark:ring-slate-900 bg-amber-500 text-white flex items-center justify-center text-[10px] font-bold">
            <User className="w-3.5 h-3.5" />
          </div>
        </div>
        <span className="ml-2 text-xs font-bold text-slate-700 dark:text-slate-300 font-mono">
          +{Math.max(0, count - 3)}
        </span>
      </div>

      {/* Safety Score / Online Status */}
      <div className="flex flex-col items-end">
        {safetyScore ? (
          <div className="flex items-center gap-1 text-amber-500 bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded-full border border-amber-200/80">
            <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
            <span className="text-xs font-extrabold font-mono text-amber-700 dark:text-amber-300">{safetyScore} / 5.0</span>
          </div>
        ) : (
          <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
            {onlineCount} On Duty
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * 4. Heavy Truck Silhouette & Telematics Odometer (For /vehicles)
 */
export function VehicleTelematicsKpi({ activeCount, maintenanceCount, avgFuel }: { activeCount: number; maintenanceCount: number; avgFuel?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 px-1 py-0.5">
      <div className="flex items-center gap-2">
        <Truck className="w-5 h-5 text-orange-500 dark:text-orange-400" />
        <div className="flex flex-col">
          <span className="text-xs font-extrabold text-slate-900 dark:text-slate-100">{activeCount} Active Freight</span>
          <span className="text-[10px] text-slate-400 font-mono">{maintenanceCount} In Service Bay</span>
        </div>
      </div>

      {avgFuel && (
        <div className="text-right">
          <span className="text-xs font-extrabold font-mono text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
            {avgFuel}
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * 5. Credit Limit vs Exposure Bar (For /customers)
 */
export function CreditExposureKpi({ usedAmount, limitAmount, currency = 'SAR' }: { usedAmount: number; limitAmount: number; currency?: string }) {
  const pct = limitAmount > 0 ? Math.min(100, Math.round((usedAmount / limitAmount) * 100)) : 0;
  const isHighRisk = pct >= 80;

  return (
    <div className="flex flex-col gap-1.5 px-1 py-0.5">
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold text-slate-500">Credit Used</span>
        <span className={cn("font-bold font-mono", isHighRisk ? "text-rose-600" : "text-slate-900 dark:text-slate-100")}>
          {currency} {usedAmount.toLocaleString()} / {limitAmount.toLocaleString()}
        </span>
      </div>

      <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden p-0.5 border border-black/[0.04]">
        <div 
          className={cn("h-full rounded-full transition-all duration-300", isHighRisk ? "bg-rose-500" : "bg-[#E8450F]")}
          style={{ width: `${pct}%` }} 
        />
      </div>
    </div>
  );
}

/**
 * 6. Payment Aging Buckets (For /invoices)
 */
export function InvoiceAgingKpi({ pendingCount, overdueCount, paidCount }: { pendingCount: number; overdueCount: number; paidCount: number }) {
  const total = pendingCount + overdueCount + paidCount || 1;
  const paidPct = Math.round((paidCount / total) * 100);
  const pendingPct = Math.round((pendingCount / total) * 100);
  const overduePct = Math.round((overdueCount / total) * 100);

  return (
    <div className="flex flex-col gap-2 px-1 py-0.5">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800 p-0.5 gap-0.5 border border-black/[0.04]">
        <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${paidPct}%` }} title={`Paid: ${paidPct}%`} />
        <div className="bg-amber-500 h-full rounded-full" style={{ width: `${pendingPct}%` }} title={`Pending: ${pendingPct}%`} />
        <div className="bg-rose-500 h-full rounded-full" style={{ width: `${overduePct}%` }} title={`Overdue: ${overduePct}%`} />
      </div>

      <div className="flex items-center justify-between text-[10px] font-mono font-bold text-slate-500">
        <span className="text-emerald-600">● {paidCount} Paid</span>
        <span className="text-amber-600">● {pendingCount} Pending</span>
        <span className="text-rose-600">● {overdueCount} Overdue</span>
      </div>
    </div>
  );
}

/**
 * 7. Freight Route Corridor Badge (For /rate-cards & /trips)
 */
export function RouteCorridorKpi({ origin = 'Riyadh', destination = 'Jeddah', tripCount = 42 }: { origin?: string; destination?: string; tripCount?: number }) {
  return (
    <div className="flex items-center justify-between gap-2 px-1 py-0.5">
      <div className="flex items-center gap-1.5 bg-indigo-50 dark:bg-indigo-950/40 px-2.5 py-1 rounded-lg border border-indigo-200/80">
        <span className="text-xs font-extrabold text-indigo-700 dark:text-indigo-300">{origin}</span>
        <ArrowRight className="w-3 h-3 text-indigo-500" />
        <span className="text-xs font-extrabold text-indigo-700 dark:text-indigo-300">{destination}</span>
      </div>

      <span className="text-[10px] font-bold font-mono text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded-md">
        {tripCount} Trips
      </span>
    </div>
  );
}

/**
 * 8. Traffic Light Expiry Countdown (For /documents & /documents/expiring)
 */
export function ExpiryCountdownKpi({ expiredCount, criticalCount, safeCount }: { expiredCount: number; criticalCount: number; safeCount: number }) {
  return (
    <div className="flex items-center justify-between gap-1.5 px-1 py-0.5">
      <div className="flex items-center gap-1 bg-rose-50 border border-rose-200 px-2 py-1 rounded-md">
        <span className="w-2 h-2 rounded-full bg-rose-600" />
        <span className="text-[10px] font-extrabold text-rose-700">{expiredCount} Expired</span>
      </div>

      <div className="flex items-center gap-1 bg-amber-50 border border-amber-200 px-2 py-1 rounded-md">
        <span className="w-2 h-2 rounded-full bg-amber-500" />
        <span className="text-[10px] font-extrabold text-amber-700">{criticalCount} &le;7d</span>
      </div>

      <div className="flex items-center gap-1 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded-md">
        <span className="w-2 h-2 rounded-full bg-emerald-500" />
        <span className="text-[10px] font-extrabold text-emerald-700">{safeCount} Valid</span>
      </div>
    </div>
  );
}
