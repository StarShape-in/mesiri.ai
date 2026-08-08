import * as React from 'react'
import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer } from '@/components/ui/chart'
import { cn } from '@/lib/utils'

export type KpiCardVariant = 'brand' | 'blue' | 'emerald' | 'amber' | 'purple' | 'rose' | 'slate'

export interface UrgencySegment {
  label?: string
  value: number
  color: string
}

export interface LivePulseTrack {
  statusText: string
  subText?: string
  pulseColor?: string
}

export interface CompletionGauge {
  percentage: number
  label: string
  subtext?: string
}

export interface PipelineStage {
  name: string
  count: number
  color: string
}

export interface RouteHealthBreakdown {
  onSchedule: number
  delayed: number
  stopped: number
}

export interface KpiCardProps extends Omit<React.ComponentProps<typeof Card>, 'title' | 'value'> {
  title?: string
  label?: string
  value: React.ReactNode
  description?: React.ReactNode
  subtitle?: React.ReactNode
  icon?: React.ReactNode | React.ElementType
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  variant?: KpiCardVariant
  chartData?: (number | { value: number; [key: string]: any })[]
  progressSegments?: UrgencySegment[]
  livePulseTrack?: LivePulseTrack
  routeHealthBreakdown?: RouteHealthBreakdown
  completionGauge?: CompletionGauge
  pipelineStages?: PipelineStage[]

  // Backward compatibility props
  delta?: string | number | null
  up?: boolean | null
  color?: string
  bg?: string
  iconVariant?: 'solid' | 'light'
}

const variantStyles: Record<KpiCardVariant, {
  cardBg: string
  accentLine: string
  iconContainer: string
  textColor: string
  chartColor: string
}> = {
  brand: {
    cardBg: '',
    accentLine: 'bg-[#E8450F]',
    iconContainer: 'bg-[#E8450F]/10 border-[#E8450F]/25 text-[#E8450F]',
    textColor: 'text-[#E8450F]',
    chartColor: '#E8450F',
  },
  blue: {
    cardBg: '',
    accentLine: 'bg-blue-500',
    iconContainer: 'bg-blue-500/10 border-blue-500/25 text-blue-600 dark:text-blue-400',
    textColor: 'text-blue-600 dark:text-blue-400',
    chartColor: '#2563EB',
  },
  emerald: {
    cardBg: '',
    accentLine: 'bg-emerald-500',
    iconContainer: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-600 dark:text-emerald-400',
    textColor: 'text-emerald-600 dark:text-emerald-400',
    chartColor: '#16A34A',
  },
  amber: {
    cardBg: '',
    accentLine: 'bg-amber-500',
    iconContainer: 'bg-amber-500/10 border-amber-500/25 text-amber-600 dark:text-amber-400',
    textColor: 'text-amber-600 dark:text-amber-400',
    chartColor: '#D97706',
  },
  purple: {
    cardBg: '',
    accentLine: 'bg-purple-500',
    iconContainer: 'bg-purple-500/10 border-purple-500/25 text-purple-600 dark:text-purple-400',
    textColor: 'text-purple-600 dark:text-purple-400',
    chartColor: '#7C3AED',
  },
  rose: {
    cardBg: '',
    accentLine: 'bg-rose-500',
    iconContainer: 'bg-rose-500/10 border-rose-500/25 text-rose-600 dark:text-rose-400',
    textColor: 'text-rose-600 dark:text-rose-400',
    chartColor: '#DC2626',
  },
  slate: {
    cardBg: '',
    accentLine: 'bg-border/60',
    iconContainer: 'bg-muted/40 border-border/50 text-muted-foreground',
    textColor: 'text-muted-foreground',
    chartColor: '#94A3B8',
  },
}

const trendGlyph = {
  up: '↑',
  down: '↓',
  neutral: '→',
} as const

const defaultChartData = [
  { index: 0, value: 24 },
  { index: 1, value: 32 },
  { index: 2, value: 28 },
  { index: 3, value: 45 },
  { index: 4, value: 39 },
  { index: 5, value: 52 },
  { index: 6, value: 60 },
]

export function KpiCard({
  title,
  label,
  value,
  description,
  subtitle,
  icon,
  trend,
  trendValue,
  variant,
  chartData,
  progressSegments,
  livePulseTrack,
  routeHealthBreakdown,
  completionGauge,
  pipelineStages,
  className,
  delta,
  up,
  color,
  bg,
  iconVariant,
  ...props
}: KpiCardProps) {
  const displayTitle = title || label || ''
  const displayDescription = description || subtitle

  let computedTrend = trend
  let computedTrendValue = trendValue

  if (!computedTrend && delta !== undefined && delta !== null) {
    const isUp = up === true || (typeof delta === 'number' && delta >= 0)
    computedTrend = isUp ? 'up' : 'down'
    if (!computedTrendValue) {
      computedTrendValue = typeof delta === 'number' ? `${Math.abs(delta)}%` : String(delta).replace(/^[+-]/, '')
    }
  }

  // Derive color variant
  let activeVariant: KpiCardVariant = variant || 'brand'
  if (!variant) {
    if (color === '#E8450F') activeVariant = 'brand'
    else if (color === '#2563EB') activeVariant = 'blue'
    else if (color === '#16A34A') activeVariant = 'emerald'
    else if (color === '#D97706') activeVariant = 'amber'
    else if (computedTrend === 'up') activeVariant = 'emerald'
    else if (computedTrend === 'down') activeVariant = 'rose'
    else activeVariant = 'brand'
  }

  const selectedStyle = variantStyles[activeVariant] || variantStyles.brand

  const rawData = (chartData && chartData.length > 0) ? chartData : defaultChartData
  const normalizedChartData = React.useMemo(() => {
    return rawData.map((item, i) => {
      if (typeof item === 'number') {
        return { index: i, value: item }
      }
      return { index: i, ...item }
    })
  }, [rawData])

  let renderedIcon: React.ReactNode = null
  if (icon) {
    if (React.isValidElement(icon)) {
      renderedIcon = React.cloneElement(icon as React.ReactElement<any>, { className: 'size-3.5' })
    } else if (typeof icon === 'function' || typeof icon === 'object') {
      renderedIcon = React.createElement(icon as React.ElementType, { className: 'size-3.5' })
    } else {
      renderedIcon = icon
    }
  }

  const gradientId = React.useId()

  return (
    <Card
      className={cn(
        'group relative rounded-none border-border/70 shadow-none p-5 gap-0 bg-white dark:bg-card',
        props.onClick && 'cursor-pointer',
        className
      )}
      {...props}
    >
      {/* Top accent rule */}
      <div
        className={cn(
          'absolute inset-x-0 top-0 h-px opacity-40',
          selectedStyle.accentLine
        )}
      />

      {/* Corner ticks — instrument-panel reference */}
      <span className="pointer-events-none absolute left-0 top-0 h-2 w-2 border-l border-t border-border/20" />
      <span className="pointer-events-none absolute bottom-0 right-0 h-2 w-2 border-b border-r border-border/20" />

      <CardHeader className="flex flex-row items-center justify-between gap-4 p-0 pb-3">
        <CardTitle className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
          {displayTitle}
        </CardTitle>
        {renderedIcon && (
          <div className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center border",
            selectedStyle.iconContainer
          )}>
            {renderedIcon}
          </div>
        )}
      </CardHeader>

      <div className="h-px bg-border/40" />

      <CardContent className="flex flex-col gap-1.5 p-0 pt-3">
        <div className="font-mono text-2xl font-bold leading-none tracking-tight text-foreground tabular-nums">
          {value}
        </div>

        {(displayDescription || computedTrendValue) && (
          <div className="flex items-baseline gap-1.5 text-[11px] font-medium leading-none">
            {computedTrend && computedTrendValue && (
              <span className={cn('inline-flex items-center gap-0.5 font-mono font-semibold tabular-nums', selectedStyle.textColor)}>
                <span aria-hidden="true">{trendGlyph[computedTrend]}</span>
                {computedTrendValue}
              </span>
            )}
            {displayDescription && (
              <span className="text-slate-500">{displayDescription}</span>
            )}
          </div>
        )}

        {/* Specialized Visual Indicator Component Area */}
        <div className="mt-3 -mx-5 -mb-5 overflow-hidden">
          {/* Mode 1: Active Route Health Breakdown (For IN TRANSIT active trips) */}
          {routeHealthBreakdown ? (
            <div className="px-5 pb-5 pt-1 flex flex-col gap-1.5">
              {/* 3-Color Route Health Bar */}
              <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800 p-0.5 gap-0.5 border border-black/[0.04]">
                <div 
                  className="bg-emerald-500 h-full rounded-full transition-all duration-300" 
                  style={{ width: `${(routeHealthBreakdown.onSchedule / (routeHealthBreakdown.onSchedule + routeHealthBreakdown.delayed + routeHealthBreakdown.stopped || 1)) * 100}%` }} 
                  title="On-Schedule"
                />
                <div 
                  className="bg-amber-500 h-full rounded-full transition-all duration-300" 
                  style={{ width: `${(routeHealthBreakdown.delayed / (routeHealthBreakdown.onSchedule + routeHealthBreakdown.delayed + routeHealthBreakdown.stopped || 1)) * 100}%` }} 
                  title="Delayed"
                />
                <div 
                  className="bg-rose-500 h-full rounded-full transition-all duration-300" 
                  style={{ width: `${(routeHealthBreakdown.stopped / (routeHealthBreakdown.onSchedule + routeHealthBreakdown.delayed + routeHealthBreakdown.stopped || 1)) * 100}%` }} 
                  title="Stopped"
                />
              </div>
              {/* Legend Badges */}
              <div className="flex items-center justify-between text-[10px] font-mono font-medium text-muted-foreground">
                <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                  {routeHealthBreakdown.onSchedule} On-Time
                </span>
                {routeHealthBreakdown.delayed > 0 && (
                  <span className="flex items-center gap-1 text-amber-700 dark:text-amber-400 font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                    {routeHealthBreakdown.delayed} Delayed
                  </span>
                )}
                {routeHealthBreakdown.stopped > 0 && (
                  <span className="flex items-center gap-1 text-rose-700 dark:text-rose-400 font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
                    {routeHealthBreakdown.stopped} Stopped
                  </span>
                )}
              </div>
            </div>
          ) : livePulseTrack ? (
            /* Mode 2: Live Pulse Track */
            <div className="px-5 pb-5 pt-1 flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-[11px] font-mono font-bold text-blue-600 dark:text-blue-400">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600"></span>
                  </span>
                  <span>{livePulseTrack.statusText}</span>
                </div>
                {livePulseTrack.subText && (
                  <span className="text-[10px] text-muted-foreground font-normal">{livePulseTrack.subText}</span>
                )}
              </div>
              <div className="w-full bg-blue-100 dark:bg-blue-950/60 h-1.5 rounded-full overflow-hidden">
                <div className="bg-blue-600 h-full rounded-full w-[74%] animate-pulse" />
              </div>
            </div>
          ) : completionGauge ? (
            /* Mode 2: Completion Ring Gauge (Donut Gauge for DELIVERED & COMPLETED) */
            <div className="px-5 pb-5 pt-0.5 flex items-center justify-between gap-3">
              <div className="flex flex-col">
                <span className="text-xs font-extrabold text-emerald-700 dark:text-emerald-400">
                  {completionGauge.label}
                </span>
                {completionGauge.subtext && (
                  <span className="text-[10px] text-muted-foreground font-mono">
                    {completionGauge.subtext}
                  </span>
                )}
              </div>
              <div className="relative w-8 h-8 shrink-0 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-slate-100 dark:text-slate-800"
                    strokeWidth="3.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className="text-emerald-500"
                    strokeDasharray={`${completionGauge.percentage}, 100`}
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <span className="absolute text-[9px] font-bold font-mono text-emerald-700 dark:text-emerald-400">
                  {completionGauge.percentage}%
                </span>
              </div>
            </div>
          ) : pipelineStages && pipelineStages.length > 0 ? (
            /* Mode 3: Pipeline Stages Stepper (Stage Cards for DISPATCH QUEUE) */
            <div className="px-5 pb-5 pt-0.5 flex flex-col gap-1.5">
              <div className="grid grid-cols-3 gap-1.5">
                {pipelineStages.map((stage, idx) => (
                  <div key={idx} className="flex flex-col p-1 rounded-md bg-slate-50 dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800">
                    <div className="flex items-center gap-1">
                      <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", stage.color)} />
                      <span className="text-[9px] font-bold text-slate-500 uppercase tracking-tight truncate">{stage.name}</span>
                    </div>
                    <span className="text-xs font-mono font-extrabold text-slate-900 dark:text-slate-100 mt-0.5">{stage.count}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : progressSegments && progressSegments.length > 0 ? (
            /* Mode 4: Segmented Urgency Progress Bar */
            <div className="px-5 pb-5 pt-1 flex flex-col gap-2">
              <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800 p-0.5 gap-0.5 border border-black/[0.04]">
                {progressSegments.map((seg, idx) => (
                  <div
                    key={idx}
                    className={cn("h-full transition-all duration-300 rounded-full", seg.color)}
                    style={{ width: `${seg.value}%` }}
                    title={seg.label ? `${seg.label}: ${seg.value}%` : undefined}
                  />
                ))}
              </div>
              {progressSegments.some(s => s.label) && (
                <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono font-medium truncate">
                  {progressSegments.map((seg, idx) => seg.label ? (
                    <span key={idx} className="flex items-center gap-1.5 truncate">
                      <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", seg.color)} />
                      <span className="truncate">{seg.label}</span>
                    </span>
                  ) : null)}
                </div>
              )}
            </div>
          ) : (
            /* Mode 5: Sparkline Area Chart */
            <div className="h-10">
              <ChartContainer
                config={{
                  value: {
                    label: 'Value',
                    color: selectedStyle.chartColor,
                  },
                }}
                className="aspect-auto h-full w-full"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={normalizedChartData} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={selectedStyle.chartColor} stopOpacity={0.25} />
                        <stop offset="100%" stopColor={selectedStyle.chartColor} stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={selectedStyle.chartColor}
                      strokeWidth={1.5}
                      fill={`url(#${gradientId})`}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </ChartContainer>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default KpiCard
