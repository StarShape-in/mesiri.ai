import { Bot, CheckCircle2, Zap, Server, Activity, Send } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface VpsHealthBarProps {
  onOpenSandbox: () => void
}

export function VpsHealthBar({ onOpenSandbox }: VpsHealthBarProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3.5 rounded-xl border border-emerald-500/30 bg-gradient-to-r from-emerald-500/10 via-emerald-500/5 to-transparent shadow-2xs">
      <div className="flex items-center gap-3">
        <div className="size-10 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0 shadow-2xs">
          <Bot className="size-5" />
        </div>

        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-foreground flex items-center gap-1.5">
              WhatsApp Assistant Engine (VPS Live)
              <span className="relative flex size-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full size-2 bg-emerald-500" />
              </span>
            </span>
            <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/20 text-[10px] font-semibold">
              v2.4 Active
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground font-medium flex items-center gap-2 mt-0.5">
            <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="size-3" /> Meta Webhook 200 OK
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Server className="size-3 text-muted-foreground" /> node-vps-01 (42ms)
            </span>
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-background/80 border text-[11px] font-mono text-muted-foreground">
          <Activity className="size-3 text-amber-500" />
          <span>Sarvam Voice • Gemini Vision • DeepSeek</span>
        </div>

        <Button
          size="sm"
          onClick={onOpenSandbox}
          className="h-8 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 shadow-2xs"
        >
          <Zap className="size-3.5" />
          <Send className="size-3" />
          Test Sandbox
        </Button>
      </div>
    </div>
  )
}
