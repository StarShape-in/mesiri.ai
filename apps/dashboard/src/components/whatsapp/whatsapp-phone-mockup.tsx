import { Bot, Check, CheckCheck, Wifi, Battery, Signal } from 'lucide-react'

interface WhatsAppPhoneMockupProps {
  activeRule: string
  lowBalanceThreshold: number
  showTransferReceipt: boolean
  showVisualCard: boolean
}

export function WhatsAppPhoneMockup({
  activeRule,
  lowBalanceThreshold,
  showVisualCard,
}: WhatsAppPhoneMockupProps) {
  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val)
  }

  return (
    <div className="w-full max-w-[340px] mx-auto rounded-[36px] border-[8px] border-slate-800 dark:border-slate-900 bg-slate-950 shadow-2xl overflow-hidden flex flex-col h-[520px] relative text-slate-100 select-none">
      {/* Phone Notch & Status Bar */}
      <div className="bg-slate-900 px-5 pt-2 pb-1.5 flex items-center justify-between text-[10px] font-semibold text-slate-400">
        <span>9:41</span>
        <div className="w-16 h-3 bg-black rounded-full mx-auto" />
        <div className="flex items-center gap-1">
          <Signal className="size-2.5" />
          <Wifi className="size-2.5" />
          <Battery className="size-3" />
        </div>
      </div>

      {/* WhatsApp App Header */}
      <div className="bg-[#075E54] dark:bg-[#128C7E] px-3 py-2 flex items-center justify-between text-white shadow-xs">
        <div className="flex items-center gap-2">
          <div className="size-7 rounded-full bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-white shrink-0">
            <Bot className="size-4" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-xs leading-tight">Mesiri AI Assistant</span>
            <span className="text-[9px] text-emerald-200">Online • VPS Connected</span>
          </div>
        </div>
      </div>

      {/* WhatsApp Chat Wall Background */}
      <div className="flex-1 p-3 bg-[#E5DDD5] dark:bg-[#0B141A] overflow-y-auto flex flex-col gap-2.5 text-xs text-slate-900 dark:text-slate-100 font-sans">
        {/* Date Divider */}
        <div className="self-center bg-white/80 dark:bg-slate-800/80 px-2.5 py-0.5 rounded-full text-[9px] text-slate-600 dark:text-slate-400 font-medium shadow-2xs">
          Today
        </div>

        {/* Dynamic Content Preview depending on active tab/rule */}
        {activeRule === 'low_balance' && (
          <>
            {/* User message */}
            <div className="self-end max-w-[82%] bg-[#DCF8C6] dark:bg-[#005C4B] p-2.5 rounded-lg rounded-tr-none shadow-2xs text-[11px] text-slate-900 dark:text-slate-100">
              <p>Check petty cash float for Riverside Site</p>
              <div className="flex items-center justify-end gap-1 text-[9px] text-slate-500 dark:text-slate-300 mt-1">
                <span>9:40 AM</span>
                <CheckCheck className="size-3 text-sky-500" />
              </div>
            </div>

            {/* Outbound Automated Alert */}
            <div className="self-start max-w-[88%] bg-white dark:bg-[#202C33] p-2.5 rounded-lg rounded-tl-none shadow-2xs text-[11px]">
              <div className="font-bold text-rose-600 dark:text-rose-400 flex items-center gap-1 mb-1">
                ⚠️ Low Petty Cash Balance Alert
              </div>
              <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
                Green Valley Housing Float is current at <strong className="font-mono text-rose-600">{formatCurrency(35000)}</strong>, which is below your safety threshold of <strong className="font-mono">{formatCurrency(lowBalanceThreshold)}</strong>.
              </p>
              <div className="mt-2 pt-1.5 border-t border-slate-200 dark:border-slate-700/60 flex items-center justify-between text-[10px]">
                <span className="text-emerald-600 font-semibold">Reply REFILL to top up</span>
                <span className="text-slate-400">9:41 AM</span>
              </div>
            </div>
          </>
        )}

        {activeRule === 'transfer_receipt' && (
          <>
            <div className="self-start max-w-[90%] bg-white dark:bg-[#202C33] p-2.5 rounded-lg rounded-tl-none shadow-2xs text-[11px]">
              <div className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mb-1">
                ✅ Funds Transferred Successfully
              </div>
              <p className="text-slate-700 dark:text-slate-300">
                <strong>₹1,00,000</strong> has been moved from <em>HDFC Corporate Account</em> to <em>Riverside Site Float</em>.
              </p>
              <div className="mt-2 bg-slate-100 dark:bg-slate-800/80 p-2 rounded text-[10px] font-mono flex flex-col gap-0.5 border">
                <div>Ref: TR-940218</div>
                <div>Custodian: Ramesh Kumar (Site PM)</div>
                <div>Status: Settled</div>
              </div>
              <div className="flex items-center justify-end text-[9px] text-slate-400 mt-1">
                <span>9:41 AM</span>
              </div>
            </div>
          </>
        )}

        {activeRule === 'expense_card' && (
          <>
            <div className="self-end max-w-[85%] bg-[#DCF8C6] dark:bg-[#005C4B] p-2 rounded-lg rounded-tr-none shadow-2xs text-[11px]">
              <p>Paid 45000 for excavator diesel at Indian Oil Bunk</p>
              <div className="flex items-center justify-end gap-1 text-[9px] text-slate-500 dark:text-slate-300 mt-1">
                <span>9:41 AM</span>
                <CheckCheck className="size-3 text-sky-500" />
              </div>
            </div>

            <div className="self-start max-w-[90%] bg-white dark:bg-[#202C33] p-2 rounded-lg rounded-tl-none shadow-2xs text-[11px] flex flex-col gap-1.5">
              <span className="font-bold text-emerald-600 dark:text-emerald-400 text-xs">
                ✅ Expense Recorded (EXP-1048)
              </span>

              {/* Render PNG Card Mockup */}
              {showVisualCard ? (
                <div className="rounded-lg overflow-hidden border border-emerald-500/30 bg-gradient-to-br from-slate-900 via-slate-850 to-slate-950 text-white p-3 font-sans shadow-md">
                  <div className="flex items-center justify-between text-[10px] text-emerald-400 font-mono border-b border-white/10 pb-1.5 mb-1.5">
                    <span>MESIRI AI RECEIPT</span>
                    <span>EXP-1048</span>
                  </div>
                  <div className="text-lg font-bold font-mono text-emerald-400">
                    ₹45,000
                  </div>
                  <div className="text-[10px] text-slate-300 mt-1">
                    Vendor: Indian Oil Bunk #4
                  </div>
                  <div className="text-[10px] text-slate-400">
                    Category: Diesel Fuel Excavator
                  </div>
                </div>
              ) : (
                <p className="text-slate-700 dark:text-slate-300 text-[11px]">
                  Recorded ₹45,000 for Fuel to Indian Oil Bunk #4.
                </p>
              )}

              <div className="flex items-center justify-between text-[9px] text-slate-400 pt-1">
                <span>Verified by DeepSeek AI</span>
                <div className="flex items-center gap-0.5">
                  <span>9:41 AM</span>
                  <Check className="size-3" />
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Mock Chat Input Footer */}
      <div className="bg-slate-900 p-2.5 flex items-center gap-2 border-t border-slate-800">
        <div className="flex-1 bg-slate-800 text-slate-400 text-[11px] px-3 py-1.5 rounded-full flex items-center justify-between">
          <span>Type a message...</span>
        </div>
        <div className="size-7 rounded-full bg-emerald-500 flex items-center justify-center text-white shrink-0">
          <Bot className="size-3.5" />
        </div>
      </div>
    </div>
  )
}
