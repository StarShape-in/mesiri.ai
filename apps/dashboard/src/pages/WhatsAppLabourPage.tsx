import * as React from 'react'
import {
  Zap,
  Smartphone,
  Terminal,
  AlertTriangle,
  Users,
  HardHat,
  BellRing,
  Clock,
  UserCheck,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { VpsHealthBar } from '@/components/whatsapp/vps-health-bar'
import { WhatsAppPhoneMockup } from '@/components/whatsapp/whatsapp-phone-mockup'
import { AutomationRuleCard } from '@/components/whatsapp/automation-rule-card'
import { PhoneMappingTable } from '@/components/whatsapp/phone-mapping-table'
import { WhatsAppTraceLogs } from '@/components/whatsapp/whatsapp-trace-logs'
import { WhatsAppLabourSandboxDialog } from '@/components/whatsapp/whatsapp-labour-sandbox-dialog'

import {
  fetchCompanySummary,
  type CompanySummary,
  fetchLabourSettingsApi,
  updateLabourSettingsApi,
} from '@/lib/api'

export default function WhatsAppLabourPage() {
  const { scope } = useScope()
  const [summary, setSummary] = React.useState<CompanySummary | null>(null)

  // Labour Automation Rule States
  const [reminderEnabled, setReminderEnabled] = React.useState(true)
  const [reminderTime, setReminderTime] = React.useState('18:00')

  const [headcountAnomalyEnabled, setHeadcountAnomalyEnabled] = React.useState(true)
  const [wageChangeAlertEnabled, setWageChangeAlertEnabled] = React.useState(true)
  const [requireApprovalForWorker, setRequireApprovalForWorker] = React.useState(false)

  React.useEffect(() => {
    let active = true
    async function loadData() {
      try {
        const [sum, settings] = await Promise.all([
          fetchCompanySummary().catch(() => null),
          fetchLabourSettingsApi().catch(() => null),
        ])
        if (active) {
          if (sum) setSummary(sum)
          if (settings) {
            if (settings.missing_report_reminder_enabled !== undefined)
              setReminderEnabled(settings.missing_report_reminder_enabled)
            if (settings.missing_report_reminder_time)
              setReminderTime(settings.missing_report_reminder_time)
            if (settings.headcount_anomaly_alert_enabled !== undefined)
              setHeadcountAnomalyEnabled(settings.headcount_anomaly_alert_enabled)
            if (settings.wage_change_alert_enabled !== undefined)
              setWageChangeAlertEnabled(settings.wage_change_alert_enabled)
            if (settings.require_dashboard_approval_for_new_worker !== undefined)
              setRequireApprovalForWorker(settings.require_dashboard_approval_for_new_worker)
          }
        }
      } catch (err) {
        console.warn('Failed to load initial data for Labour WhatsApp page:', err)
      }
    }
    loadData()
    return () => {
      active = false
    }
  }, [])

  // Automation Rule Tab state
  const [activeRuleTab, setActiveRuleTab] = React.useState('missing_reminder')
  // Sandbox Dialog State
  const [sandboxOpen, setSandboxOpen] = React.useState(false)

  const handleToggleReminder = async (enabled: boolean) => {
    setReminderEnabled(enabled)
    try {
      await updateLabourSettingsApi({ missing_report_reminder_enabled: enabled })
    } catch (err) {
      console.warn('Failed to update missing report reminder setting:', err)
    }
  }

  const handleReminderTimeChange = async (time: string) => {
    setReminderTime(time)
    try {
      await updateLabourSettingsApi({ missing_report_reminder_time: time })
    } catch (err) {
      console.warn('Failed to update reminder time:', err)
    }
  }

  const handleToggleHeadcountAnomaly = async (enabled: boolean) => {
    setHeadcountAnomalyEnabled(enabled)
    try {
      await updateLabourSettingsApi({ headcount_anomaly_alert_enabled: enabled })
    } catch (err) {
      console.warn('Failed to update headcount anomaly setting:', err)
    }
  }

  const handleToggleWageChangeAlert = async (enabled: boolean) => {
    setWageChangeAlertEnabled(enabled)
    try {
      await updateLabourSettingsApi({ wage_change_alert_enabled: enabled })
    } catch (err) {
      console.warn('Failed to update wage change alert setting:', err)
    }
  }

  const handleToggleRequireApproval = async (enabled: boolean) => {
    setRequireApprovalForWorker(enabled)
    try {
      await updateLabourSettingsApi({ require_dashboard_approval_for_new_worker: enabled })
    } catch (err) {
      console.warn('Failed to update require approval setting:', err)
    }
  }

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Organization Site Labor Triggers)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-amber-500/30 bg-amber-500/10 flex items-center justify-center text-amber-600 dark:text-amber-400 shrink-0 shadow-2xs">
            <HardHat className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Labour WhatsApp Automations
              <Badge variant="outline" className="text-[10px] font-mono border-amber-500/30 text-amber-600 dark:text-amber-400">
                Workforce Assistant
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>
      </div>

      {/* VPS Bot Live Health Banner */}
      <VpsHealthBar onOpenSandbox={() => setSandboxOpen(true)} />

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Active Automations"
          value={<span className="text-amber-600 dark:text-amber-400">4 Active Triggers</span>}
          trend="up"
          trendValue="VPS Active"
          description="Attendance, Anomaly, Reminders"
          icon={<Zap className="text-amber-500" />}
          chartData={[15, 20, 35, 40, 60, 75]}
        />
        <KpiCard
          title="Registered Personnel"
          value={
            <span className="text-blue-600 dark:text-blue-400">
              {summary ? `${summary.total_users} Members` : 'Live DB'}
            </span>
          }
          trend="neutral"
          trendValue="Site Supervisors"
          description="Site personnel & foremen"
          icon={<Smartphone className="text-blue-500" />}
        />
        <KpiCard
          title="Active Projects"
          value={
            <span className="text-purple-600 dark:text-purple-400">
              {summary ? `${summary.total_projects} Projects` : 'Live DB'}
            </span>
          }
          trend="up"
          trendValue="Live Tracking"
          description="Managed site scopes"
          icon={<Users className="text-purple-500" />}
        />
        <KpiCard
          title="Active Sites"
          value={
            <span className="text-emerald-600 dark:text-emerald-400">
              {summary ? `${summary.total_sites} Sites` : 'Live DB'}
            </span>
          }
          trend="neutral"
          trendValue="Site Locations"
          description="Active construction sites"
          icon={<BellRing className="text-emerald-500" />}
        />
      </div>

      {/* Core Tabs: Automations vs Custodians vs Logs */}
      <Tabs defaultValue="automations" className="w-full">
        <TabsList className="w-full sm:w-auto grid grid-cols-3 h-9 bg-muted/60 p-1">
          <TabsTrigger value="automations" className="text-xs gap-1.5 font-semibold">
            <Zap className="size-3.5 text-amber-500" />
            Automations & Triggers
          </TabsTrigger>
          <TabsTrigger value="custodians" className="text-xs gap-1.5 font-semibold">
            <Smartphone className="size-3.5 text-blue-500" />
            Supervisor Phone Mappings
          </TabsTrigger>
          <TabsTrigger value="logs" className="text-xs gap-1.5 font-semibold">
            <Terminal className="size-3.5 text-purple-500" />
            WhatsApp Activity Audit Log
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Automations & Triggers */}
        <TabsContent value="automations" className="pt-3">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* Left Column: Rule Cards list */}
            <div className="lg:col-span-7 flex flex-col gap-3">
              <h2 className="text-sm font-bold text-foreground flex items-center justify-between border-b pb-2">
                <span>Configure Labour WhatsApp Triggers</span>
                <span className="text-[11px] text-muted-foreground font-normal">
                  Click a rule card to preview on phone
                </span>
              </h2>

              <AutomationRuleCard
                id="missing_reminder"
                title="Missing Daily Attendance Reminder"
                description="Automatically sends a daily WhatsApp nudge at specified time to site engineers if no attendance report was submitted."
                enabled={reminderEnabled}
                icon={<Clock className="size-4" />}
                badgeText="Daily Nudge"
                active={activeRuleTab === 'missing_reminder'}
                onSelect={() => setActiveRuleTab('missing_reminder')}
                onToggle={handleToggleReminder}
                scheduleValue={reminderTime}
                onScheduleChange={handleReminderTimeChange}
              />

              <AutomationRuleCard
                id="headcount_anomaly"
                title="Headcount Anomaly & Spike Warning"
                description="Sends an alert to project manager if reported daily headcount deviates by >30% from the site 7-day average."
                enabled={headcountAnomalyEnabled}
                icon={<AlertTriangle className="size-4" />}
                badgeText="Anomaly Alert"
                active={activeRuleTab === 'headcount_anomaly'}
                onSelect={() => setActiveRuleTab('headcount_anomaly')}
                onToggle={handleToggleHeadcountAnomaly}
              />

              <AutomationRuleCard
                id="wage_change"
                title="Daily Wage Rate Change Notification"
                description="Sends instant alert to finance controller whenever a supervisor submits an attendance report with an updated wage rate."
                enabled={wageChangeAlertEnabled}
                icon={<HardHat className="size-4" />}
                badgeText="Wage Rate Policy"
                active={activeRuleTab === 'wage_change'}
                onSelect={() => setActiveRuleTab('wage_change')}
                onToggle={handleToggleWageChangeAlert}
              />

              <AutomationRuleCard
                id="worker_approval"
                title="New Worker Dashboard Approval Policy"
                description="Requires project manager approval on web dashboard before a newly reported worker can be added to permanent master roster."
                enabled={requireApprovalForWorker}
                icon={<UserCheck className="size-4" />}
                badgeText="Roster Policy"
                active={activeRuleTab === 'worker_approval'}
                onSelect={() => setActiveRuleTab('worker_approval')}
                onToggle={handleToggleRequireApproval}
              />
            </div>

            {/* Right Column: Live Phone Mockup Preview */}
            <div className="lg:col-span-5 flex flex-col items-center gap-2 border p-4 rounded-xl bg-card/40 sticky top-4">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Smartphone className="size-4 text-amber-500" />
                Live WhatsApp Screen Mockup
              </span>
              <p className="text-[11px] text-muted-foreground text-center mb-2">
                Real-time preview of how labor attendance messages appear on supervisor phones.
              </p>

              <WhatsAppPhoneMockup
                activeRule={activeRuleTab}
                lowBalanceThreshold={50000}
                showTransferReceipt={true}
                showVisualCard={true}
              />
            </div>
          </div>
        </TabsContent>

        {/* Tab 2: Custodians & Phone Mappings */}
        <TabsContent value="custodians" className="pt-3">
          <PhoneMappingTable />
        </TabsContent>

        {/* Tab 3: Live Trace Stream */}
        <TabsContent value="logs" className="pt-3">
          <WhatsAppTraceLogs />
        </TabsContent>
      </Tabs>

      {/* Testing Sandbox Modal */}
      <WhatsAppLabourSandboxDialog open={sandboxOpen} onOpenChange={setSandboxOpen} />
    </div>
  )
}
