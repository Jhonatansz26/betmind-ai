import type { MarketRow } from '@/lib/betmind'
import { cn } from '@/lib/utils'

const VERDICT_META: Record<string, { className: string; label: string }> = {
  'EV+': { className: 'border border-positive/30 bg-positive/10 text-positive', label: 'POSITIVE_EV' },
  'POSITIVE_EV': { className: 'border border-positive/30 bg-positive/10 text-positive', label: 'POSITIVE_EV' },
  MARGINAL: { className: 'border border-border/50 bg-surface text-muted-foreground', label: 'NO_VALUE' },
  'NO EDGE': { className: 'border border-border/50 bg-surface text-muted-foreground', label: 'NO_VALUE' },
  NO_VALUE: { className: 'border border-border/50 bg-surface text-muted-foreground', label: 'NO_VALUE' },
  AVOID: { className: 'border border-border/50 bg-surface text-muted-foreground', label: 'AVOID' },
  NO_ODDS_AVAILABLE: { className: 'text-subtle opacity-60', label: 'SIN CUOTAS' },
}

export function MarketTable({ rows }: { rows: MarketRow[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border/60 bg-card text-xs">
      <table className="w-full min-w-[620px]">
        <thead className="bg-surface/40">
          <tr className="divide-border/40">
            {['Mercado', 'Prob. modelo', 'Cuota casa', 'Implícita', 'Edge', 'EV', 'Veredicto'].map((label, index) => (
              <th key={label} className={cn('px-3 py-2 text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground', index > 0 && 'text-right')}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {rows.map((row) => {
            const verdict = VERDICT_META[row.verdict] ?? VERDICT_META.NO_VALUE
            return (
              <tr key={row.key} className="transition-colors hover:bg-surface/40">
                <td className="px-3 py-2.5 font-medium text-foreground">{row.label}</td>
                <td className="px-3 py-2.5 text-right font-mono font-medium tabular-nums text-foreground">{(row.probability * 100).toFixed(1)}%</td>
                <td className="px-3 py-2.5 text-right font-mono font-medium tabular-nums text-foreground">{row.odds > 1 ? row.odds.toFixed(2) : '—'}</td>
                <td className="px-3 py-2.5 text-right font-mono font-medium tabular-nums text-foreground">{row.implied ? `${(row.implied * 100).toFixed(1)}%` : '—'}</td>
                <td className={cn('px-3 py-2.5 text-right font-mono font-medium tabular-nums', row.edge >= 0 ? 'text-positive' : 'text-foreground')}>{row.edge >= 0 ? '+' : ''}{(row.edge * 100).toFixed(1)}%</td>
                <td className={cn('px-3 py-2.5 text-right font-mono font-medium tabular-nums', row.ev >= 0 ? 'text-positive' : 'text-foreground')}>{row.ev >= 0 ? '+' : ''}{(row.ev * 100).toFixed(1)}%</td>
                <td className="px-3 py-2.5 text-right">
                  <span className={cn('inline-flex rounded px-2 py-0.5 font-mono text-[10px] font-bold', verdict.className)}>{verdict.label}</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
