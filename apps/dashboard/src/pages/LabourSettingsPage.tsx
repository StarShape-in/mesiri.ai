import * as React from 'react'
import {
  SlidersHorizontal,
  Save,
  Clock,
  AlertTriangle,
  UserCheck,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { useToast } from '@/components/ui/toast-notification'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  fetchLabourSettingsApi,
  updateLabourSettingsApi,
  type LabourSettingsItem,
} from '@/lib/api'

export default function LabourSettingsPage() {
  const { scope } = useScope()
  const toast = useToast()

  const [saving, setSaving] = React.useState(false)

  // Labour Settings State
  const [reminderEnabled, setReminderEnabled] = React.useState(true)
  const [reminderTime, setReminderTime] = React.useState('18:00')
  const [headcountAnomalyEnabled, setHeadcountAnomalyEnabled] = React.useState(true)
  const [wageChangeAlertEnabled, setWageChangeAlertEnabled] = React.useState(true)
  const [requireApprovalForWorker, setRequireApprovalForWorker] = React.useState(false)
  const [defaultDailyWage, setDefaultDailyWage] = React.useState('800')

  const loadSettings = React.useCallback(async () => {
    try {
      const data = await fetchLabourSettingsApi()
      if (data) {
        if (data.missing_report_reminder_enabled !== undefined) setReminderEnabled(data.missing_report_reminder_enabled)
        if (data.missing_report_reminder_time) setReminderTime(data.missing_report_reminder_time)
        if (data.headcount_anomaly_alert_enabled !== undefined) setHeadcountAnomalyEnabled(data.headcount_anomaly_alert_enabled)
        if (data.wage_change_alert_enabled !== undefined) setWageChangeAlertEnabled(data.wage_change_alert_enabled)
        if (data.require_dashboard_approval_for_new_worker !== undefined) setRequireApprovalForWorker(data.require_dashboard_approval_for_new_worker)
      }
    } catch (err) {
      console.warn('Failed to load labour settings from backend:', err)
    }
  }, [])

  React.useEffect(() => {
    loadSettings()
  }, [loadSettings])

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload: Partial<LabourSettingsItem> = {
        missing_report_reminder_enabled: reminderEnabled,
        missing_report_reminder_time: reminderTime,
        headcount_anomaly_alert_enabled: headcountAnomalyEnabled,
        wage_change_alert_enabled: wageChangeAlertEnabled,
        require_dashboard_approval_for_new_worker: requireApprovalForWorker,
      }
      await updateLabourSettingsApi(payload)
      toast.success('Labour settings saved', 'Organization workforce policies updated successfully')
    } catch (err: any) {
      console.warn('Failed to update labour settings:', err)
      const detail = err?.response?.data?.detail
      const msg = Array.isArray(detail) ? detail.join(', ') : detail || err.message || 'Server connection error'
      toast.error('Failed to save settings', msg)
    } finally {
      setSaving(false)
    }
  }

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Site Labor Policies)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">
      {/* Page Header */}
      <form onSubmit={handleSaveSettings}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5 mb-4">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-lg border border-amber-500/30 bg-amber-500/10 flex items-center justify-center text-amber-600 dark:text-amber-400 shrink-0 shadow-2xs">
              <SlidersHorizontal className="size-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
                Labour & Workforce Settings
                <Badge variant="outline" className="text-[10px] font-mono border-amber-500/30 text-amber-600 dark:text-amber-400">
                  Workforce Module
                </Badge>
              </h1>
              <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
            </div>
          </div>

          <Button
            type="submit"
            disabled={saving}
            className="h-8 gap-1.5 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-2xs self-start sm:self-auto"
          >
            <Save className="size-3.5" />
            {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>

        {/* Tabbed Settings Sections */}
        <Tabs defaultValue="automations" className="w-full space-y-4">
          <TabsList className="w-full sm:w-auto grid grid-cols-3 h-9 bg-muted/60 p-1">
            <TabsTrigger value="automations" className="text-xs gap-1.5 font-semibold">
              <Clock className="size-3.5 text-amber-500" />
              Automations & Nudges
            </TabsTrigger>
            <TabsTrigger value="alerts" className="text-xs gap-1.5 font-semibold">
              <AlertTriangle className="size-3.5 text-rose-500" />
              Anomaly & Alerts
            </TabsTrigger>
            <TabsTrigger value="roster" className="text-xs gap-1.5 font-semibold">
              <UserCheck className="size-3.5 text-blue-500" />
              Roster & Approvals
            </TabsTrigger>
          </TabsList>

          {/* Tab 1: Automations & Nudges */}
          <TabsContent value="automations">
            <Card className="p-4 border shadow-2xs space-y-4 bg-card">
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                  <Clock className="size-4 text-amber-500" />
                  Daily Attendance Reminder Nudges
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Configure automated WhatsApp nudges sent to site supervisors if no attendance report was submitted for the day.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t">
                <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                  <div className="space-y-0.5">
                    <Label className="text-xs font-semibold text-foreground">Enable Daily Reminder Nudges</Label>
                    <p className="text-[11px] text-muted-foreground">Send automated WhatsApp nudge to missing sites</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={reminderEnabled}
                    onChange={(e) => setReminderEnabled(e.target.checked)}
                    className="size-4 rounded border-border text-amber-600 focus:ring-amber-500 cursor-pointer accent-amber-600"
                  />
                </div>

                <div className="space-y-1.5 p-3 rounded-lg border bg-muted/20">
                  <Label className="text-xs font-semibold text-foreground">Daily Reminder Execution Time</Label>
                  <Select value={reminderTime} onValueChange={setReminderTime} disabled={!reminderEnabled}>
                    <SelectTrigger className="h-9 text-xs">
                      <SelectValue placeholder="Select Execution Time" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="17:00">5:00 PM (17:00 IST)</SelectItem>
                      <SelectItem value="18:00">6:00 PM (18:00 IST - Default)</SelectItem>
                      <SelectItem value="19:00">7:00 PM (19:00 IST)</SelectItem>
                      <SelectItem value="20:00">8:00 PM (20:00 IST)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </Card>
          </TabsContent>

          {/* Tab 2: Anomaly & Alerts */}
          <TabsContent value="alerts">
            <Card className="p-4 border shadow-2xs space-y-4 bg-card">
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                  <AlertTriangle className="size-4 text-rose-500" />
                  Headcount Anomaly & Wage Rate Alerts
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Configure alert triggers sent to project managers and finance controllers for unusual site labor activities.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t">
                <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                  <div className="space-y-0.5">
                    <Label className="text-xs font-semibold text-foreground">Headcount Anomaly Warning</Label>
                    <p className="text-[11px] text-muted-foreground">Alert manager if daily site headcount deviates by &gt;30%</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={headcountAnomalyEnabled}
                    onChange={(e) => setHeadcountAnomalyEnabled(e.target.checked)}
                    className="size-4 rounded border-border text-amber-600 focus:ring-amber-500 cursor-pointer accent-amber-600"
                  />
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                  <div className="space-y-0.5">
                    <Label className="text-xs font-semibold text-foreground">Daily Wage Rate Change Notification</Label>
                    <p className="text-[11px] text-muted-foreground">Notify finance controller when supervisor submits updated wage rate</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={wageChangeAlertEnabled}
                    onChange={(e) => setWageChangeAlertEnabled(e.target.checked)}
                    className="size-4 rounded border-border text-amber-600 focus:ring-amber-500 cursor-pointer accent-amber-600"
                  />
                </div>
              </div>
            </Card>
          </TabsContent>

          {/* Tab 3: Roster & Approvals */}
          <TabsContent value="roster">
            <Card className="p-4 border shadow-2xs space-y-4 bg-card">
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                  <UserCheck className="size-4 text-blue-500" />
                  Roster & Registration Approval Policies
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Govern master worker registrations and baseline daily wage thresholds.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t">
                <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                  <div className="space-y-0.5">
                    <Label className="text-xs font-semibold text-foreground">New Worker Web Approval Policy</Label>
                    <p className="text-[11px] text-muted-foreground">Require dashboard manager approval before new worker joins master roster</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={requireApprovalForWorker}
                    onChange={(e) => setRequireApprovalForWorker(e.target.checked)}
                    className="size-4 rounded border-border text-amber-600 focus:ring-amber-500 cursor-pointer accent-amber-600"
                  />
                </div>

                <div className="space-y-1.5 p-3 rounded-lg border bg-muted/20">
                  <Label className="text-xs font-semibold text-foreground">Baseline Daily Wage (₹)</Label>
                  <Input
                    type="number"
                    value={defaultDailyWage}
                    onChange={(e) => setDefaultDailyWage(e.target.value)}
                    className="h-9 text-xs font-mono"
                    placeholder="800"
                  />
                </div>
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </form>
    </div>
  )
}
