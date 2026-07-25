import * as React from 'react'
import {
  Bot,
  Zap,
  Smartphone,
  Terminal,
  AlertTriangle,
  ArrowLeftRight,
  CreditCard,
  BellRing,
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
import { WhatsAppSandboxDialog } from '@/components/whatsapp/whatsapp-sandbox-dialog'

export default function WhatsAppFinancePage() {
  const { scope } = useScope()

  // Automation Rule States
  const [activeRuleTab, setActiveRuleTab] = React.useState('low_balance')

  // Rule Toggles & Values
  const [lowBalanceEnabled, setLowBalanceEnabled] = React.useState(true)
  const [lowBalanceThreshold, setLowBalanceThreshold] = React.useState(50000)

  const [transferReceiptEnabled, setTransferReceiptEnabled] = React.useState(true)

  const [expenseCardEnabled, setExpenseCardEnabled] = React.useState(true)
  const [showVisualCard] = React.useState(true)

  const [weeklyDigestEnabled, setWeeklyDigestEnabled] = React.useState(true)
  const [weeklyDigestSchedule, setWeeklyDigestSchedule] = React.useState('weekly_monday')

  // Sandbox Dialog State
  const [sandboxOpen, setSandboxOpen] = React.useState(false)

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Organization WhatsApp Triggers)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0 shadow-2xs">
            <Bot className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              WhatsApp Assistant & Automations
              <Badge variant="outline" className="text-[10px] font-mono border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
                Finance Integration
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
          value={<span className="text-emerald-600 dark:text-emerald-400">5 Live Rules</span>}
          trend="up"
          trendValue="VPS Active"
          description="Automated trigger rules"
          icon={<Zap className="text-emerald-500" />}
          chartData={[10, 15, 25, 30, 45, 50]}
        />
        <KpiCard
          title="Registered Custodians"
          value={<span className="text-blue-600 dark:text-blue-400">18 Numbers</span>}
          trend="neutral"
          trendValue="Site Personnel"
          description="Verified WhatsApp accounts"
          icon={<Smartphone className="text-blue-500" />}
        />
        <KpiCard
          title="PNG Cards Rendered"
          value={<span className="text-purple-600 dark:text-purple-400">342 Receipts</span>}
          trend="up"
          trendValue="Playwright Engine"
          description="Visual receipt generation"
          icon={<CreditCard className="text-purple-500" />}
        />
        <KpiCard
          title="Float Alerts Triggered"
          value={<span className="text-amber-600 dark:text-amber-400">12 Sent</span>}
          trend="neutral"
          trendValue="Low Balance Warnings"
          description="Petty cash refill notifications"
          icon={<BellRing className="text-amber-500" />}
        />
      </div>

      {/* Core Tabs: Automations vs Custodians vs Logs */}
      <Tabs defaultValue="automations" className="w-full">
        <TabsList className="w-full sm:w-auto grid grid-cols-3 h-9 bg-muted/60 p-1">
          <TabsTrigger value="automations" className="text-xs gap-1.5 font-semibold">
            <Zap className="size-3.5 text-emerald-500" />
            Automations & Triggers
          </TabsTrigger>
          <TabsTrigger value="custodians" className="text-xs gap-1.5 font-semibold">
            <Smartphone className="size-3.5 text-blue-500" />
            Custodian Phone Mappings
          </TabsTrigger>
          <TabsTrigger value="logs" className="text-xs gap-1.5 font-semibold">
            <Terminal className="size-3.5 text-purple-500" />
            Live Trace Stream
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Automations & Triggers (Split-View Rule Builder + Phone Mockup) */}
        <TabsContent value="automations" className="pt-3">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* Left Column: Rule Cards list */}
            <div className="lg:col-span-7 flex flex-col gap-3">
              <h2 className="text-sm font-bold text-foreground flex items-center justify-between border-b pb-2">
                <span>Configure WhatsApp Triggers</span>
                <span className="text-[11px] text-muted-foreground font-normal">
                  Click a rule card to preview on phone
                </span>
              </h2>

              <AutomationRuleCard
                id="low_balance"
                title="Low Petty Cash Float Warning"
                description="Automatically sends a WhatsApp alert to the Site PM & Finance Controller when site petty cash drops below threshold."
                enabled={lowBalanceEnabled}
                icon={<AlertTriangle className="size-4" />}
                badgeText="Treasury Alert"
                active={activeRuleTab === 'low_balance'}
                onSelect={() => setActiveRuleTab('low_balance')}
                onToggle={setLowBalanceEnabled}
                thresholdValue={lowBalanceThreshold}
                onThresholdChange={setLowBalanceThreshold}
              />

              <AutomationRuleCard
                id="transfer_receipt"
                title="Inter-Account Transfer Confirmation"
                description="Sends an instant WhatsApp transfer receipt to the site custodian when funds are moved on the web dashboard."
                enabled={transferReceiptEnabled}
                icon={<ArrowLeftRight className="size-4" />}
                badgeText="Transfer Receipt"
                active={activeRuleTab === 'transfer_receipt'}
                onSelect={() => setActiveRuleTab('transfer_receipt')}
                onToggle={setTransferReceiptEnabled}
              />

              <AutomationRuleCard
                id="expense_card"
                title="Post-Confirmation PNG Receipt Cards"
                description="Renders a Jinja2 Playwright visual PNG receipt card and replies on WhatsApp whenever an expense is logged."
                enabled={expenseCardEnabled}
                icon={<CreditCard className="size-4" />}
                badgeText="Visual Card"
                active={activeRuleTab === 'expense_card'}
                onSelect={() => setActiveRuleTab('expense_card')}
                onToggle={setExpenseCardEnabled}
              />

              <AutomationRuleCard
                id="weekly_digest"
                title="Weekly Outstanding Expense Digest"
                description="Sends an automated summary of unpaid vendor expenses to finance managers every Monday morning."
                enabled={weeklyDigestEnabled}
                icon={<BellRing className="size-4" />}
                badgeText="Scheduled Cron"
                active={activeRuleTab === 'weekly_digest'}
                onSelect={() => setActiveRuleTab('weekly_digest')}
                onToggle={setWeeklyDigestEnabled}
                scheduleValue={weeklyDigestSchedule}
                onScheduleChange={setWeeklyDigestSchedule}
              />
            </div>

            {/* Right Column: Live Phone Mockup Preview */}
            <div className="lg:col-span-5 flex flex-col items-center gap-2 border p-4 rounded-xl bg-card/40 sticky top-4">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Smartphone className="size-4 text-emerald-500" />
                Live WhatsApp Screen Mockup
              </span>
              <p className="text-[11px] text-muted-foreground text-center mb-2">
                Real-time preview of how messages appear on field worker phones.
              </p>

              <WhatsAppPhoneMockup
                activeRule={activeRuleTab}
                lowBalanceThreshold={lowBalanceThreshold}
                showTransferReceipt={transferReceiptEnabled}
                showVisualCard={showVisualCard}
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
      <WhatsAppSandboxDialog open={sandboxOpen} onOpenChange={setSandboxOpen} />
    </div>
  )
}
