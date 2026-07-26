import * as React from 'react'
import {
  ClipboardCheck,
  Calendar,
  DollarSign,
  Users,
  HardHat,
  ImageIcon,
  Bot,
  Globe,
} from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
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
} from '@/lib/api'

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

  React.useEffect(() => {
    if (reportId && open) {
      setLoading(true)
      fetchAttendanceReportDetailApi(reportId)
        .then((data) => setDetail(data))
        .catch((err) => {
          console.warn('Failed to load attendance report details:', err)
          setDetail(null)
        })
        .finally(() => setLoading(false))
    } else {
      setDetail(null)
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
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {!detail.lines || detail.lines.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="h-20 text-center text-xs text-muted-foreground">
                            No trade lines recorded for this report.
                          </TableCell>
                        </TableRow>
                      ) : (
                        detail.lines.map((line, idx) => {
                          const rate = line.daily_wage || 0
                          const subtotal = rate * (line.headcount || 1)
                          return (
                            <TableRow key={line.id || idx} className="hover:bg-muted/30">
                              <TableCell className="py-2 text-xs">
                                <div className="flex flex-col">
                                  <span className="font-semibold text-foreground flex items-center gap-1.5">
                                    <HardHat className="size-3 text-amber-500" />
                                    {line.trade || line.worker_name || 'General Labor'}
                                  </span>
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
                    {detail.attachments.map((att, idx) => (
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
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
