import * as React from 'react'
import {
  RefreshCw,
  Save,
  Sliders,
  Bell,
  MessageSquare,
  HardHat,
  FileCheck,
  Clock,
  Plus,
  Trash2,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import {
  fetchOperationsSettingsApi,
  updateOperationsSettingsApi,
} from '@/lib/api'
import { useToast } from '@/components/ui/toast-notification'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { cn } from '@/lib/utils'

// ─── Custom Switch Component ──────────────────────────────────────────────────

function ToggleSwitch({ checked, onCheckedChange }: { checked: boolean; onCheckedChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none',
        checked ? 'bg-indigo-600' : 'bg-muted-foreground/30'
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block size-4 rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out',
          checked ? 'translate-x-4' : 'translate-x-0'
        )}
      />
    </button>
  )
}

// ─── Main Operations Settings Page ─────────────────────────────────────────────

export default function OperationsSettingsPage() {
  const { scope } = useScope()
  const toast = useToast()

  const [loading, setLoading] = React.useState<boolean>(true)
  const [saving, setSaving] = React.useState<boolean>(false)

  // Settings State
  const [autoApproveDprs, setAutoApproveDprs] = React.useState<boolean>(false)
  const [requirePhotoEvidence, setRequirePhotoEvidence] = React.useState<boolean>(true)
  const [allowOverrunQuantities, setAllowOverrunQuantities] = React.useState<boolean>(false)
  const [defaultShift, setDefaultShift] = React.useState<string>('DAY')
  const [whatsappNudgeHours, setWhatsappNudgeHours] = React.useState<number>(18)
  const [autoFlagWeatherDelays, setAutoFlagWeatherDelays] = React.useState<boolean>(true)
  const [phoneNumbers, setPhoneNumbers] = React.useState<string[]>([])
  const [newPhoneInput, setNewPhoneInput] = React.useState<string>('')

  const loadSettings = React.useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchOperationsSettingsApi()
      if (res) {
        setAutoApproveDprs(Boolean(res.auto_approve_dprs))
        setRequirePhotoEvidence(Boolean(res.require_photo_evidence))
        setAllowOverrunQuantities(Boolean(res.allow_overrun_quantities))
        setDefaultShift(res.default_shift || 'DAY')
        setWhatsappNudgeHours(res.whatsapp_nudge_hours || 18)
        setAutoFlagWeatherDelays(Boolean(res.auto_flag_weather_delays))
        setPhoneNumbers(res.supervisor_phone_numbers || [])
      }
    } catch {
      // Defaults already set
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadSettings()
  }, [loadSettings])

  const handleAddPhone = () => {
    if (!newPhoneInput.trim()) return
    setPhoneNumbers((prev) => [...prev, newPhoneInput.trim()])
    setNewPhoneInput('')
  }

  const handleRemovePhone = (index: number) => {
    setPhoneNumbers((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSaveSettings = async () => {
    setSaving(true)
    try {
      await updateOperationsSettingsApi({
        auto_approve_dprs: autoApproveDprs,
        require_photo_evidence: requirePhotoEvidence,
        allow_overrun_quantities: allowOverrunQuantities,
        default_shift: defaultShift,
        whatsapp_nudge_hours: whatsappNudgeHours,
        auto_flag_weather_delays: autoFlagWeatherDelays,
        supervisor_phone_numbers: phoneNumbers,
      })
      toast.success('Operations Policies Saved', 'Updated organization site progress rules in database.')
    } catch {
      toast.error('Save Failed', 'Could not update site operation settings.')
    } finally {
      setSaving(false)
    }
  }

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Projects)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">

      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-indigo-500/30 bg-indigo-500/10 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0 shadow-2xs">
            <Sliders className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Site Operations Settings
              <Badge variant="outline" className="text-[10px] font-mono border-indigo-500/30 text-indigo-600 dark:text-indigo-400">
                Organization Policy
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            disabled={saving}
            onClick={handleSaveSettings}
            className="h-8 gap-1.5 text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-2xs"
          >
            {saving ? <RefreshCw className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
            Save Policy Changes
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={loadSettings}
            disabled={loading}
            className="h-8 gap-1.5 text-xs"
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
            Reload
          </Button>
        </div>
      </div>

      {/* ── Settings Grid Cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* 1. DPR Approval & Execution Rules */}
        <Card className="rounded-lg border-border/80 shadow-2xs">
          <CardHeader className="border-b bg-muted/10 pb-3">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <FileCheck className="size-4 text-indigo-600" />
              DPR Pipeline & Approval Rules
            </CardTitle>
            <CardDescription className="text-xs">
              Configure validation rules for Daily Progress Report submissions
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4 space-y-4 text-xs">
            <div className="flex items-center justify-between gap-4 p-3 rounded-lg border bg-muted/10">
              <div className="space-y-0.5">
                <span className="font-bold text-foreground block">Auto-Approve DPR Submissions</span>
                <span className="text-[11px] text-muted-foreground block">
                  Automatically freeze & verify DPRs without requiring site manager sign-off.
                </span>
              </div>
              <ToggleSwitch checked={autoApproveDprs} onCheckedChange={setAutoApproveDprs} />
            </div>

            <div className="flex items-center justify-between gap-4 p-3 rounded-lg border bg-muted/10">
              <div className="space-y-0.5">
                <span className="font-bold text-foreground block">Mandatory Photo Evidence</span>
                <span className="text-[11px] text-muted-foreground block">
                  Require at least 1 site photo attachment for quantity updates.
                </span>
              </div>
              <ToggleSwitch checked={requirePhotoEvidence} onCheckedChange={setRequirePhotoEvidence} />
            </div>

            <div className="flex items-center justify-between gap-4 p-3 rounded-lg border bg-muted/10">
              <div className="space-y-0.5">
                <span className="font-bold text-foreground block">Allow Overrun Quantities</span>
                <span className="text-[11px] text-muted-foreground block">
                  Permit site engineers to log executed quantities above planned targets.
                </span>
              </div>
              <ToggleSwitch checked={allowOverrunQuantities} onCheckedChange={setAllowOverrunQuantities} />
            </div>
          </CardContent>
        </Card>

        {/* 2. WhatsApp Automations & Reminders */}
        <Card className="rounded-lg border-border/80 shadow-2xs">
          <CardHeader className="border-b bg-muted/10 pb-3">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <MessageSquare className="size-4 text-emerald-600" />
              WhatsApp Automations & Nudges
            </CardTitle>
            <CardDescription className="text-xs">
              Automated WhatsApp reminders and weather delay flags
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4 space-y-4 text-xs">
            <div className="space-y-1.5 p-3 rounded-lg border bg-muted/10">
              <label className="font-bold text-foreground block">Daily WhatsApp Nudge Schedule</label>
              <span className="text-[11px] text-muted-foreground block mb-2">
                Time when automated DPR collection prompts are sent to site supervisors.
              </span>
              <Select value={String(whatsappNudgeHours)} onValueChange={(val) => setWhatsappNudgeHours(parseInt(val, 10))}>
                <SelectTrigger className="h-9 text-xs">
                  <Clock className="size-3.5 mr-1.5 text-muted-foreground" />
                  <SelectValue placeholder="Select Nudge Time" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="17">17:00 (5:00 PM Evening Nudge)</SelectItem>
                  <SelectItem value="18">18:00 (6:00 PM Shift End Nudge)</SelectItem>
                  <SelectItem value="19">19:00 (7:00 PM Night Summary)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between gap-4 p-3 rounded-lg border bg-muted/10">
              <div className="space-y-0.5">
                <span className="font-bold text-foreground block">Auto-Flag Weather Delays</span>
                <span className="text-[11px] text-muted-foreground block">
                  Automatically create site issue records when severe weather interruptions are reported.
                </span>
              </div>
              <ToggleSwitch checked={autoFlagWeatherDelays} onCheckedChange={setAutoFlagWeatherDelays} />
            </div>
          </CardContent>
        </Card>

        {/* 3. Default Shift Configuration */}
        <Card className="rounded-lg border-border/80 shadow-2xs">
          <CardHeader className="border-b bg-muted/10 pb-3">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <HardHat className="size-4 text-sky-600" />
              Site Shift & Operations Defaults
            </CardTitle>
            <CardDescription className="text-xs">
              Default working shifts for site reporting
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4 space-y-4 text-xs">
            <div className="space-y-1.5">
              <label className="font-bold text-foreground block">Default Working Shift</label>
              <Select value={defaultShift} onValueChange={setDefaultShift}>
                <SelectTrigger className="h-9 text-xs">
                  <SelectValue placeholder="Select Shift" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="DAY">DAY SHIFT (08:00 - 17:00)</SelectItem>
                  <SelectItem value="NIGHT">NIGHT SHIFT (20:00 - 05:00)</SelectItem>
                  <SelectItem value="SPLIT">SPLIT SHIFT</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* 4. Supervisor Notification Alert List */}
        <Card className="rounded-lg border-border/80 shadow-2xs">
          <CardHeader className="border-b bg-muted/10 pb-3">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Bell className="size-4 text-amber-600" />
              Supervisor Escalation Alerts
            </CardTitle>
            <CardDescription className="text-xs">
              WhatsApp phone numbers that receive critical blocker alerts
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4 space-y-3 text-xs">
            <div className="flex items-center gap-2">
              <Input
                placeholder="+91 98765 43210"
                value={newPhoneInput}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewPhoneInput(e.target.value)}
                className="h-8 text-xs font-mono"
              />
              <Button size="sm" onClick={handleAddPhone} className="h-8 text-xs font-bold gap-1 bg-indigo-600 text-white">
                <Plus className="size-3.5" /> Add
              </Button>
            </div>

            <div className="space-y-1.5 pt-2">
              {phoneNumbers.length === 0 ? (
                <p className="text-muted-foreground text-[11px] italic">No escalation phone numbers added.</p>
              ) : (
                phoneNumbers.map((phone, idx) => (
                  <div key={idx} className="flex items-center justify-between p-2 rounded border bg-muted/20 text-xs font-mono">
                    <span>{phone}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemovePhone(idx)}
                      className="h-5 size-5 p-0 text-muted-foreground hover:text-rose-600"
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  )
}
