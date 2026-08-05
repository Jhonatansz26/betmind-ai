import type { TicketLegData } from '@/lib/betmind'
import { cn } from '@/lib/utils'

export function TicketLeg({ leg, index = 0 }: { leg: TicketLegData; index?: number }) {
  const evPositive = leg.ev > 0
  const evText = `${evPositive ? '+' : ''}${(leg.ev * 100).toFixed(1)}% EV`

  return (
    <li
      title="Cuota de bookmaker comparada contra probabilidad desmarquinizada de modelo Poisson"
      className="stagger-item flex items-center justify-between gap-3 border-b border-border/40 px-3.5 py-2.5 last:border-b-0 transition-colors hover:bg-surface/40"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-xs font-semibold text-foreground">{leg.market}</span>
        <span className="block truncate text-[11px] leading-tight text-muted-foreground" title={leg.match}>
          {leg.match}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <span className={cn(
          'rounded border px-1.5 py-0.5 font-mono text-xs font-bold tabular-nums',
          evPositive
            ? 'border-positive/20 bg-positive/10 text-positive'
            : 'border-negative/20 bg-negative/10 text-negative',
        )}>
          {evText}
        </span>
        <span className="font-mono text-sm font-bold tabular-nums text-foreground">@{leg.odds.toFixed(2)}</span>
      </div>
    </li>
  )
}
