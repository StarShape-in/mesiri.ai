import * as React from 'react'
import {
  ClipboardCheck,
  Calendar,
  DollarSign,
  Users,
  HardHat,
  ImageIcon,
  ImageOff,
  AlertCircle,
  Bot,
  Globe,
  Link2,
  UserPlus,
} from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  fetchAttendanceReportDetailApi,
  type LabourAttendanceDetailItem,
  type LabourAttendanceLineItem,
} from '@/lib/api'
import { AddWorkerDialog } from './add-worker-dialog'

interface AttendanceDetailSheetProps {
  reportId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AttendanceDetailSheet({
  reportId,
  open,
  onOpenChange,
}: AttendanceDetailSheetProps) {
  const [detail, setDetail] = React.useState<LabourAttendanceDetailItem | null>(null)
  const [loading, setLoading] = React.useState(false)
  // Surfaced, not swallowed. This used to console.warn and render an empty
  // sheet, so a failing request looked identical to a report with no workers
  // in it -- which is exactly how a 500 here got reported as "the worker
  // names are missing".
  const [loadError, setLoadError] = React.useState<string | null>(null)
  // The line currently being promoted -- drives both the "Save as permanent
  // worker" dialog's open state and what it's pre-filled with. null means
  // closed; kept as the whole line (not just booleans) so the dialog can
  // read name/trade/wage straight off it.
  const [promotingLine, setPromotingLine] = React.useState<LabourAttendanceLineItem | null>(null)

  React.useEffect(() => {
    if (reportId && open) {
      setLoading(true)
      setLoadError(null)
      fetchAttendanceReportDetailApi(reportId)
        .then((data) => setDetail(data))
        .catch((err) => {
          console.warn('Failed to load attendance report details:', err)
          setDetail(null)
          setLoadError(
            "Couldn't load this report's details. The attendance itself is safely recorded — please try again, or refresh the page.",
          )
        })
        .finally(() => setLoading(false))
    } else {
      setDetail(null)
      setLoadError(null)
    }
  }, [reportId, open])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[560px] flex flex-col justify-between overflow-y-auto">
        <div className="space-y-4">
          <SheetHeader className="pb-2 border-b">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <div className="p-1.5 rounded-md bg-amber-500/10 border border-amber-500/20">
                <ClipboardCheck className="size-5" />
              </div>
              <div className="flex items-center gap-2">
                <SheetTitle className="text-base font-bold">Attendance Report Detail</SheetTitle>
                {detail && (
                  <Badge
                    variant="outline"
                    className={
                      detail.recorded_via?.includes('whatsapp')
                        ? 'border-emerald-500/30 text-emerald-600 bg-emerald-500/10 text-[10px]'
                        : 'border-blue-500/30 text-blue-600 bg-blue-500/10 text-[10px]'
                    }
                  >
                    {detail.recorded_via?.includes('whatsapp') ? (
                      <span className="flex items-center gap-1">
                        <Bot className="size-3" /> WhatsApp Bot
                      </span>
                    ) : (
                      <span className="flex items-center gap-1">
                        <Globe className="size-3" /> Web Entry
                      </span>
                    )}
                  </Badge>
                )}
              </div>
            </div>
            <SheetDescription className="text-xs">
              Detailed daily site labor log, trade breakdowns, wages, and photo proof.
            </SheetDescription>
          </SheetHeader>

          {loading ? (
            <div className="py-12 text-center text-xs text-muted-foreground">
              Loading report details...
            </div>
          ) : loadError ? (
            <div className="py-10 px-4 flex flex-col items-center gap-2 text-center">
              <AlertCircle className="size-5 text-amber-600 dark:text-amber-400" />
              <p className="text-xs text-foreground max-w-[320px]">{loadError}</p>
            </div>
          ) : !detail ? (
            <div className="py-12 text-center text-xs text-muted-foreground">
              Attendance report details not found.
            </div>
          ) : (
            <div className="space-y-4 text-xs">
              {/* Summary Stats Header Bar */}
              <div className="grid grid-cols-3 gap-2.5 p-3 rounded-lg border bg-gradient-to-br from-card via-card to-amber-500/5">
                <div className="flex flex-col">
                  <span className="text-[10px] text-muted-foreground font-medium flex items-center gap-1">
                    <Calendar className="size-3 text-amber-500" /> Report Date
                  </span>
                  <span className="font-bold text-foreground text-xs mt-0.5">
                    {detail.occurred_date}
                  </span>
                </div>

                <div className="flex flex-col">
                  <span className="text-[10px] text-muted-foreground font-medium flex items-center gap-1">
                    <Users className="size-3 text-blue-500" /> Total Headcount
                  </span>
                  <span className="font-bold text-foreground text-xs mt-0.5">
                    {detail.total_headcount} Workers
                  </span>
                </div>

                <div className="flex flex-col">
                  <span className="text-[10px] text-muted-foreground font-medium flex items-center gap-1">
                    <DollarSign className="size-3 text-emerald-500" /> Total Wage Cost
                  </span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400 text-xs font-mono mt-0.5">
                    ₹{detail.total_cost.toLocaleString('en-IN')}
                  </span>
                </div>
              </div>

              {/* Notes */}
              {detail.notes && (
                <div className="p-2.5 rounded-md bg-muted/40 border text-xs">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase block mb-0.5">
                    Site Notes / Task Summary
                  </span>
                  <p className="text-foreground">{detail.notes}</p>
                </div>
              )}

              {/* Line Items Table */}
              <div className="space-y-1.5">
                <span className="font-bold text-xs flex items-center justify-between text-foreground">
                  <span>Worker Trade Breakdown ({detail.lines?.length || 0} Lines)</span>
                </span>

                <div className="border rounded-md overflow-hidden bg-card">
                  <Table>
                    <TableHeader className="bg-muted/40">
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="text-[11px] font-semibold h-8">Trade / Worker</TableHead>
                        <TableHead className="text-[11px] font-semibold h-8 text-center">Headcount</TableHead>
                        <TableHead className="text-[11px] font-semibold h-8 text-right">Daily Wage</TableHead>
                        <TableHead className="text-[11px] font-semibold h-8 text-right">Subtotal</TableHead>
                        <TableHead className="text-[11px] font-semibold h-8" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {!detail.lines || detail.lines.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={5} className="h-20 text-center text-xs text-muted-foreground">
                            No trade lines recorded for this report.
                          </TableCell>
                        </TableRow>
                      ) : (
                        detail.lines.map((line, idx) => {
                          const rate = line.daily_wage || 0
                          const subtotal = rate * (line.headcount || 1)
                          // A headcount group ("12 helpers") names nobody --
                          // there is no one to match or promote, so the
                          // matched/temporary distinction (which is about a
                          // specific person) simply doesn't apply to it.
                          const isNamedWorker = Boolean(line.worker_name)
                          const isMatched = Boolean(line.worker_id)
                          return (
                            <TableRow key={line.id || idx} className="hover:bg-muted/30">
                              <TableCell className="py-2 text-xs">
                                <div className="flex flex-col gap-0.5">
                                  <span className="font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
                                    <HardHat className="size-3 text-amber-500 shrink-0" />
                                    {isNamedWorker ? (
                                      <>
                                        {line.worker_name}
                                        {line.trade && (
                                          <span className="font-normal text-muted-foreground">
                                            — {line.trade}
                                          </span>
                                        )}
                                      </>
                                    ) : (
                                      <>{line.trade || 'General Labor'}</>
                                    )}
                                    {isNamedWorker && (
                                      <Badge
                                        variant="outline"
                                        className={
                                          isMatched
                                            ? 'border-emerald-500/30 text-emerald-600 bg-emerald-500/10 text-[9px] gap-0.5 px-1.5 py-0 h-4'
                                            : 'border-amber-500/30 text-amber-600 bg-amber-500/10 text-[9px] gap-0.5 px-1.5 py-0 h-4'
                                        }
                                      >
                                        {isMatched ? (
                                          <>
                                            <Link2 className="size-2.5" /> Register
                                          </>
                                        ) : (
                                          'Temporary'
                                        )}
                                      </Badge>
                                    )}
                                  </span>
                                  {/* The reading as originally written, e.g. a
                                      Malayalam script name -- shown so a
                                      mis-transliteration is catchable here the
                                      same way it is at WhatsApp confirmation
                                      (workflows/labour_update/nodes.py's
                                      _line_summary). */}
                                  {line.worker_name_original &&
                                    line.worker_name_original !== line.worker_name && (
                                      <span className="text-[10px] text-muted-foreground">
                                        As written: {line.worker_name_original}
                                      </span>
                                    )}
                                  {line.contractor && (
                                    <span className="text-[10px] text-muted-foreground">
                                      Contractor: {line.contractor}
                                    </span>
                                  )}
                                  {line.activity && (
                                    <span className="text-[10px] text-muted-foreground italic">
                                      Task: {line.activity}
                                    </span>
                                  )}
                                </div>
                              </TableCell>

                              <TableCell className="py-2 text-xs text-center font-semibold">
                                {line.headcount}
                              </TableCell>

                              <TableCell className="py-2 text-xs text-right font-mono">
                                {rate ? `₹${rate.toLocaleString('en-IN')}` : '—'}
                              </TableCell>

                              <TableCell className="py-2 text-xs text-right font-mono font-bold text-foreground">
                                {subtotal ? `₹${subtotal.toLocaleString('en-IN')}` : '—'}
                              </TableCell>

                              <TableCell className="py-2 text-xs text-right">
                                {isNamedWorker && !isMatched && (
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    className="h-6 text-[10px] px-2 gap-1"
                                    onClick={() => setPromotingLine(line)}
                                  >
                                    <UserPlus className="size-3" />
                                    Save as worker
                                  </Button>
                                )}
                              </TableCell>
                            </TableRow>
                          )
                        })
                      )}
                    </TableBody>
                  </Table>
                </div>
              </div>

              {/* Attachments Section */}
              {detail.attachments && detail.attachments.length > 0 && (
                <div className="space-y-2 pt-2 border-t">
                  <span className="font-bold text-xs text-foreground flex items-center gap-1.5">
                    <ImageIcon className="size-4 text-purple-500" />
                    Site Photo Proof ({detail.attachments.length})
                  </span>

                  <div className="grid grid-cols-2 gap-2">
                    {detail.attachments.map((att, idx) =>
                      att.url ? (
                        <a
                          key={att.id || idx}
                          href={att.url}
                          target="_blank"
                          rel="noreferrer"
                          className="group relative rounded-lg border overflow-hidden bg-muted/40 aspect-video flex items-center justify-center hover:border-amber-500 transition-colors"
                        >
                          <img
                            src={att.url}
                            alt="Site Attendance Proof"
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                          />
                          <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-[10px] font-bold">
                            Click to Expand
                          </div>
                        </a>
                      ) : (
                        // The photo was captured but can't be served right
                        // now. Say so plainly rather than rendering a broken
                        // image, and never hide the attendance data behind it.
                        <div
                          key={att.id || idx}
                          className="rounded-lg border border-dashed bg-muted/30 aspect-video flex flex-col items-center justify-center gap-1 text-center px-2"
                        >
                          <ImageOff className="size-4 text-muted-foreground" />
                          <span className="text-[10px] text-muted-foreground leading-tight">
                            Photo unavailable
                          </span>
                        </div>
                      ),
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </SheetContent>

      {/* Attendance never writes the register as a side effect of recording
          (principle P1) -- this dialog is the explicit, separate act that
          promotes a temporary line into it, pre-filled with what the site
          already reported so nobody retypes a name and trade that were
          already typed once on WhatsApp. */}
      <AddWorkerDialog
        open={promotingLine !== null}
        onOpenChange={(next) => {
          if (!next) setPromotingLine(null)
        }}
        onSuccess={() => setPromotingLine(null)}
        initialValues={
          promotingLine
            ? {
                name: promotingLine.worker_name ?? undefined,
                trade: promotingLine.trade ?? undefined,
                dailyWage: promotingLine.daily_wage,
                contractor: promotingLine.contractor,
              }
            : undefined
        }
      />
    </Sheet>
  )
}
