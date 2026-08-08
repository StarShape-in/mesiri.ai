import * as React from 'react'

/**
 * MERCON KPI icon set — custom line-art icons for the dashboard stat ("KPI") cards.
 *
 * Style: single-color line drawings on a 24×24 grid, stroke = `currentColor`
 * (so each KpiCard tints them via its `color` prop), ~1.6 stroke, rounded joins.
 * A few carry a light accent detail (motion lines, arrow, cap) for character —
 * matching the brand's illustrative logistics look. Sized by the consumer
 * (KpiCard renders them large; default 24px otherwise).
 */

type IconProps = React.SVGProps<SVGSVGElement>

function Svg({ children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  )
}

/** Box truck with speed lines — trips / movement. */
export const TruckMotion = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7.5 6h6.5v10H7.5z" />
    <path d="M14 10h3l2.4 2.8V16H14" />
    <circle cx="10" cy="17.2" r="1.7" />
    <circle cx="17" cy="17.2" r="1.7" />
    <path d="M1.5 8.5h3M1 12h3.6M1.5 15.5h3" opacity="0.5" />
  </Svg>
)

/** Container truck (with ridges) — active fleet. */
export const FleetTruck = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 6.5h9v10H3z" />
    <path d="M12 10h3.2l2.6 3V16.5H12" />
    <path d="M6 6.5v10M9 6.5v10" opacity="0.5" />
    <circle cx="7" cy="17.6" r="1.7" />
    <circle cx="15.5" cy="17.6" r="1.7" />
  </Svg>
)

/** Banknote + coin — revenue / money. */
export const MoneyBills = (p: IconProps) => (
  <Svg {...p}>
    <rect x="2.5" y="6.5" width="19" height="11" rx="1.8" />
    <circle cx="12" cy="12" r="2.6" />
    <path d="M6 9.6h.01M18 14.4h.01" />
  </Svg>
)

/** Ascending bars + trend arrow — growth / revenue trend. */
export const RevenueChart = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.5 20h17" />
    <path d="M6.5 20v-3.5M11 20v-6M15.5 20v-8.5" opacity="0.45" />
    <path d="M4.5 13 9 9l3 2 6.5-6" />
    <path d="M18.5 5h-3M18.5 5v3" />
  </Svg>
)

/** Calendar with an alert mark — renewals / expiry due. */
export const CalendarAlert = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 9.5h18" />
    <path d="M8 3v3.5M16 3v3.5" />
    <path d="M12 12.5v3" />
    <path d="M12 18h.01" />
  </Svg>
)

/** Warning triangle — risk / overdue. */
export const RiskAlert = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <path d="M12 9v4.5" />
    <path d="M12 17h.01" />
  </Svg>
)

/** Person with a cap — drivers. */
export const DriverBadge = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="9.5" r="3" />
    <path d="M8.8 8.2a3.2 3.2 0 0 1 6.4 0" />
    <path d="M15.2 8.2H17" />
    <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
  </Svg>
)

/** Heartbeat / pulse line — activity / rates. */
export const ActivityPulse = (p: IconProps) => (
  <Svg {...p}>
    <path d="M2.5 12H7l2-6 4 12 2-6h4.5" />
  </Svg>
)

/** Wrench — maintenance. */
export const MaintenanceWrench = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  </Svg>
)

/** Gear — settings / maintenance cost. */
export const Gear = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v2.5M12 19.5V22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M2 12h2.5M19.5 12H22M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
  </Svg>
)

/** Document with lines — invoices / documents. */
export const InvoiceDoc = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 3h8l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
    <path d="M14 3v4h4" />
    <path d="M9 12.5h6M9 15.5h6M9 18h4" />
  </Svg>
)

/** Circle with a check — done / available / paid. */
export const CheckBadge = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M8.5 12.3l2.4 2.4 4.7-5.1" />
  </Svg>
)

/** Route with endpoints — trips / routes. */
export const RouteLine = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="6" cy="19" r="2.6" />
    <path d="M8.6 19h8.4a3.4 3.4 0 0 0 0-6.8H7a3.4 3.4 0 0 1 0-6.8h7.4" />
    <circle cx="18" cy="5" r="2.6" />
  </Svg>
)

/** Office building — customers / companies. */
export const CustomerBuilding = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16" />
    <path d="M14 9h4a1 1 0 0 1 1 1v11" />
    <path d="M3 21h18" />
    <path d="M7 8h3M7 11.5h3M7 15h3" />
  </Svg>
)

/** Clock — outstanding / time. */
export const ClockIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 1.8" />
  </Svg>
)
