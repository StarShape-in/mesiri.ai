import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface AutomationRuleCardProps {
  id: string
  title: string
  description: string
  enabled: boolean
  icon: React.ReactNode
  badgeText: string
  active: boolean
  onSelect: () => void
  onToggle: (enabled: boolean) => void
  thresholdValue?: number
  onThresholdChange?: (val: number) => void
  scheduleValue?: string
  onScheduleChange?: (val: string) => void
}

export function AutomationRuleCard({
  title,
  description,
  enabled,
  icon,
  badgeText,
  active,
  onSelect,
  onToggle,
  thresholdValue,
  onThresholdChange,
  scheduleValue,
  onScheduleChange,
}: AutomationRuleCardProps) {
  return (
    <Card
      className={`p-4 transition-all duration-200 cursor-pointer relative border ${
        active
          ? 'border-emerald-500/60 ring-1 ring-emerald-500/30 bg-gradient-to-r from-emerald-500/10 via-card to-card shadow-xs'
          : 'hover:border-primary/40 bg-card/60'
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div
            className={`p-2 rounded-lg border shrink-0 ${
              enabled
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                : 'bg-muted border-border text-muted-foreground'
            }`}
          >
            {icon}
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-sm text-foreground">{title}</h3>
              <Badge
                variant="outline"
                className="text-[10px] border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
              >
                {badgeText}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
          </div>
        </div>

        {/* Toggle Switch */}
        <div className="flex items-center shrink-0" onClick={(e) => e.stopPropagation()}>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => onToggle(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600" />
          </label>
        </div>
      </div>

      {/* Conditional Configuration Controls when rule is enabled */}
      {enabled && active && (
        <div
          className="mt-3 pt-3 border-t grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs"
          onClick={(e) => e.stopPropagation()}
        >
          {thresholdValue !== undefined && onThresholdChange && (
            <div className="space-y-1">
              <Label className="text-[11px] font-semibold text-muted-foreground">
                Minimum Float Alert Threshold (₹)
              </Label>
              <Input
                type="number"
                value={thresholdValue}
                onChange={(e) => onThresholdChange(Number(e.target.value))}
                className="h-8 text-xs font-mono font-bold"
              />
            </div>
          )}

          {scheduleValue !== undefined && onScheduleChange && (
            <div className="space-y-1">
              <Label className="text-[11px] font-semibold text-muted-foreground">
                Digest Dispatch Schedule
              </Label>
              <Select value={scheduleValue} onValueChange={onScheduleChange}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select schedule" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily_9am">Every Day at 9:00 AM</SelectItem>
                  <SelectItem value="weekly_monday">Every Monday at 9:00 AM</SelectItem>
                  <SelectItem value="monthly_1st">1st of Every Month</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-1 col-span-full">
            <Label className="text-[11px] font-semibold text-muted-foreground">
              Target Recipients
            </Label>
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20 text-[10px]">
                Site Managers
              </Badge>
              <Badge className="bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/20 text-[10px]">
                Finance Controller
              </Badge>
              <Badge className="bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20 text-[10px]">
                Treasury Lead
              </Badge>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}
