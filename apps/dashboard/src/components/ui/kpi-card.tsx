import * as React from 'react'
import { Area, AreaChart } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer } from '@/components/ui/chart'
import { cn } from '@/lib/utils'

export interface KpiCardProps extends React.ComponentProps<typeof Card> {
  title: string
  value: React.ReactNode
  description?: React.ReactNode
  icon?: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  chartData?: (number | { value: number; [key: string]: any })[]
}

const trendColor = {
  up: 'text-emerald-600 dark:text-emerald-400',
  down: 'text-rose-600 dark:text-rose-400',
  neutral: 'text-muted-foreground',
} as const

const trendAccent = {
  up: 'bg-emerald-500/50 group-hover:bg-emerald-500',
  down: 'bg-rose-500/50 group-hover:bg-rose-500',
  neutral: 'bg-border/50 group-hover:bg-border',
} as const

const trendIconContainer = {
  up: 'bg-emerald-500/8 border-emerald-500/20 text-emerald-600 dark:text-emerald-400 group-hover:border-emerald-500/40 group-hover:bg-emerald-500/15',
  down: 'bg-rose-500/8 border-rose-500/20 text-rose-600 dark:text-rose-400 group-hover:border-rose-500/40 group-hover:bg-rose-500/15',
  neutral: 'bg-muted/40 border-border/50 text-muted-foreground group-hover:border-border group-hover:text-foreground',
} as const

const trendGlyph = {
  up: '↑',
  down: '↓',
  neutral: '→',
} as const

export function KpiCard({
  title,
  value,
  description,
  icon,
  trend,
  trendValue,
  chartData,
  className,
  ...props
}: KpiCardProps) {
  const hasChart = chartData && chartData.length > 0
  const normalizedChartData = React.useMemo(() => {
    if (!hasChart) return []
    return chartData.map((item, i) => {
      if (typeof item === 'number') {
        return { index: i, value: item }
      }
      return { index: i, ...item }
    })
  }, [chartData, hasChart])

  return (
    <Card
      className={cn(
        'group relative rounded-none border-border/70 shadow-none transition-all duration-200 hover:border-border py-4 gap-0 bg-gradient-to-b from-card via-card to-transparent',
        trend === 'up' && 'to-emerald-500/[0.015] dark:to-emerald-400/[0.008]',
        trend === 'down' && 'to-rose-500/[0.015] dark:to-rose-400/[0.008]',
        className
      )}
      {...props}
    >
      {/* Top accent rule — visible but quiet by default, lights up on hover */}
      <div
        className={cn(
          'absolute inset-x-0 top-0 h-px opacity-40 transition-opacity duration-200 group-hover:opacity-100',
          trend ? trendAccent[trend] : 'bg-border'
        )}
      />

      {/* Corner ticks — signature detail, instrument-panel reference */}
      <span className="pointer-events-none absolute left-0 top-0 h-2 w-2 border-l border-t border-border/20 transition-colors duration-200 group-hover:border-border" />
      <span className="pointer-events-none absolute bottom-0 right-0 h-2 w-2 border-b border-r border-border/20 transition-colors duration-200 group-hover:border-border" />

      <CardHeader className="flex flex-row items-center justify-between gap-4 px-4 pb-2.5 pt-0">
        <CardTitle className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          {title}
        </CardTitle>
        {icon && (
          <div className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center border transition-all duration-200",
            trend ? trendIconContainer[trend] : trendIconContainer.neutral
          )}>
            {React.isValidElement(icon)
              ? React.cloneElement(icon as React.ReactElement<any>, { className: 'size-3.5' })
              : icon}
          </div>
        )}
      </CardHeader>

      <div className="mx-4 h-px bg-border/60" />

      <CardContent className="flex flex-col gap-1.5 px-4 pt-2.5 pb-0">
        <div className="font-mono text-2xl font-semibold leading-none tracking-tight text-foreground tabular-nums">
          {value}
        </div>

        {(description || trendValue) && (
          <div className="flex items-baseline gap-1.5 text-[11px]">
            {trend && trendValue && (
              <span className={cn('inline-flex items-center gap-0.5 font-mono font-medium tabular-nums', trendColor[trend])}>
                <span aria-hidden="true">{trendGlyph[trend]}</span>
                {trendValue}
              </span>
            )}
            {description && (
              <span className="text-muted-foreground">{description}</span>
            )}
          </div>
        )}

        {hasChart && (
          <div className={cn(
            "mt-2 -mx-4 -mb-4 h-8 overflow-hidden",
            trend === 'up' && "text-emerald-500/80 dark:text-emerald-400/80",
            trend === 'down' && "text-rose-500/80 dark:text-rose-400/80",
            (!trend || trend === 'neutral') && "text-muted-foreground/30"
          )}>
            <ChartContainer
              config={{
                value: {
                  label: 'Value',
                },
              }}
              className="aspect-auto h-full w-full"
            >
              <AreaChart data={normalizedChartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="currentColor"
                  strokeWidth={1}
                  fill="currentColor"
                  fillOpacity={0.04}
                />
              </AreaChart>
            </ChartContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
