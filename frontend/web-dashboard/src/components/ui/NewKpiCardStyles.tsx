import * as React from 'react';
import { cn } from '@/lib/utils';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

/**
 * 1. HeroStatBanner — Wide prominent telemetry banner card
 */
export function HeroStatBanner({
  title,
  mainValue,
  subLabel,
  trend,
  trendValue,
  icon: Icon,
  badgeText,
  accentColor = 'brand',
  onClick,
  children,
}: {
  title: string;
  mainValue: React.ReactNode;
  subLabel?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  icon?: React.ElementType;
  badgeText?: string;
  accentColor?: 'brand' | 'indigo' | 'emerald' | 'amber' | 'rose';
  onClick?: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div 
      onClick={onClick}
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-white dark:bg-card p-5 shadow-xs",
        onClick && "cursor-pointer"
      )}
    >
      <div className="flex items-center justify-between gap-4 mb-3">
        <div className="flex items-center gap-2">
          {Icon && (
            <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-slate-800 shadow-2xs flex items-center justify-center text-slate-800 dark:text-slate-200">
              <Icon className="w-4 h-4" />
            </div>
          )}
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {title}
          </span>
        </div>

        {badgeText && (
          <span className="text-[10px] font-extrabold uppercase tracking-wide px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 shadow-2xs">
            {badgeText}
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-3">
        <div className="text-3xl font-extrabold font-mono tracking-tight text-slate-900 dark:text-slate-100">
          {mainValue}
        </div>

        {trendValue && (
          <div className={cn(
            "flex items-center text-xs font-bold font-mono px-2 py-0.5 rounded-md",
            trend === 'up' ? "text-emerald-700 bg-emerald-50" : trend === 'down' ? "text-rose-700 bg-rose-50" : "text-slate-600 bg-slate-100"
          )}>
            {trend === 'up' ? <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" /> : trend === 'down' ? <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" /> : null}
            {trendValue}
          </div>
        )}
      </div>

      {subLabel && <p className="text-xs text-slate-500 font-medium mt-1">{subLabel}</p>}

      {children && <div className="mt-3 pt-3 border-t border-slate-200/60 dark:border-slate-800">{children}</div>}
    </div>
  );
}

/**
 * 2. GlassmeterCard — Glassmorphic rounded meter card
 */
export function GlassmeterCard({
  title,
  value,
  subtitle,
  icon: Icon,
  percentage,
  meterColor = 'bg-emerald-500',
  onClick,
}: {
  title: string;
  value: React.ReactNode;
  subtitle?: string;
  icon?: React.ElementType;
  percentage?: number;
  meterColor?: string;
  onClick?: () => void;
}) {
  return (
    <div 
      onClick={onClick}
      className={cn(
        "relative rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-card p-4 shadow-2xs flex flex-col justify-between",
        onClick && "cursor-pointer"
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">{title}</span>
        {Icon && <Icon className="w-4 h-4 text-slate-400" />}
      </div>

      <div className="flex items-baseline justify-between gap-2 my-1">
        <span className="text-2xl font-extrabold font-mono text-slate-900 dark:text-slate-100">{value}</span>
        {percentage !== undefined && (
          <span className="text-xs font-bold font-mono text-slate-600 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">
            {percentage}%
          </span>
        )}
      </div>

      {percentage !== undefined && (
        <div className="w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden my-1.5">
          <div className={cn("h-full rounded-full transition-all duration-500", meterColor)} style={{ width: `${percentage}%` }} />
        </div>
      )}

      {subtitle && <span className="text-[10px] font-medium text-slate-400 mt-1">{subtitle}</span>}
    </div>
  );
}

/**
 * 3. TelemetryDarkCard — Dark high-tech telemetry slate card
 */
export function TelemetryDarkCard({
  title,
  value,
  statusText,
  icon: Icon,
  pulseColor = 'bg-emerald-400',
  onClick,
  children,
}: {
  title: string;
  value: React.ReactNode;
  statusText?: string;
  icon?: React.ElementType;
  pulseColor?: string;
  onClick?: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div 
      onClick={onClick}
      className={cn(
        "relative rounded-2xl bg-slate-950 text-white p-4 shadow-md border border-slate-800 flex flex-col justify-between overflow-hidden",
        onClick && "cursor-pointer"
      )}
    >
      <div className="flex items-center justify-between mb-3 z-10">
        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{title}</span>
        {statusText && (
          <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-800/60">
            <span className={cn("w-1.5 h-1.5 rounded-full animate-pulse", pulseColor)} />
            {statusText}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between z-10">
        <span className="text-3xl font-extrabold font-mono tracking-tight text-white">{value}</span>
        {Icon && <Icon className="w-6 h-6 text-indigo-400 opacity-80" />}
      </div>

      {children && <div className="mt-3 z-10">{children}</div>}
    </div>
  );
}

/**
 * 4. CompactCapsulePill — Pill-shaped stat container
 */
export function CompactCapsulePill({
  title,
  value,
  badgeText,
  icon: Icon,
  accentColor = 'border-slate-200 bg-white dark:bg-card',
  onClick,
}: {
  title: string;
  value: React.ReactNode;
  badgeText?: string;
  icon?: React.ElementType;
  accentColor?: string;
  onClick?: () => void;
}) {
  return (
    <div 
      onClick={onClick}
      className={cn(
        "flex items-center justify-between p-3.5 rounded-2xl border shadow-2xs bg-white dark:bg-card",
        onClick && "cursor-pointer",
        accentColor
      )}
    >
      <div className="flex items-center gap-3">
        {Icon && (
          <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-800 shadow-2xs flex items-center justify-center text-slate-800 dark:text-slate-200 shrink-0">
            <Icon className="w-4 h-4" />
          </div>
        )}
        <div className="flex flex-col">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{title}</span>
          <span className="text-xl font-extrabold font-mono text-slate-900 dark:text-slate-100">{value}</span>
        </div>
      </div>

      {badgeText && (
        <span className="text-xs font-bold font-mono px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
          {badgeText}
        </span>
      )}
    </div>
  );
}
