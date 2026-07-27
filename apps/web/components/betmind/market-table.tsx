import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { MarketRow } from '@/lib/betmind'
import { cn } from '@/lib/utils'

const VERDICT_META: Record<MarketRow['verdict'], { icon: string; className: string; label: string }> = {
  'EV+': { icon: '✅', className: 'text-positive', label: 'VALOR (+EV)' },
  MARGINAL: { icon: '⚪', className: 'text-muted-foreground', label: 'MARGINAL' },
  'NO EDGE': { icon: '❌', className: 'text-subtle', label: 'SIN EDGE' },
  AVOID: { icon: '❌', className: 'text-negative', label: 'EVITAR' },
}

export function MarketTable({ rows }: { rows: MarketRow[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <Table className="min-w-[560px]">
        <TableHeader>
          <TableRow className="border-border">
            <TableHead className="text-xs text-subtle">Mercado</TableHead>
            <TableHead className="text-right text-xs text-subtle">Nuestra Prob.</TableHead>
            <TableHead className="text-right text-xs text-subtle">Cuota</TableHead>
            <TableHead className="text-right text-xs text-subtle">Implícita</TableHead>
            <TableHead className="text-right text-xs text-subtle">Edge</TableHead>
            <TableHead className="text-right text-xs text-subtle">VE</TableHead>
            <TableHead className="text-right text-xs text-subtle">Veredicto</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const verdict = VERDICT_META[row.verdict]
            const isEvPositive = row.verdict === 'EV+'
            const isAvoid = row.verdict === 'AVOID'

            return (
              <TableRow
                key={row.key}
                className={cn(
                  'border-border/60 transition-colors',
                  isEvPositive && 'bg-positive/[0.04] hover:bg-positive/[0.08]',
                )}
              >
                <TableCell className="text-sm font-semibold text-foreground">{row.label}</TableCell>
                <TableCell className="num text-right text-sm text-muted-foreground">
                  {`${(row.probability * 100).toFixed(1)}%`}
                </TableCell>
                <TableCell className="num text-right text-sm font-medium text-foreground">
                  {row.odds.toFixed(2)}
                </TableCell>
                <TableCell className="num text-right text-sm text-muted-foreground">
                  {`${(row.implied * 100).toFixed(1)}%`}
                </TableCell>
                <TableCell
                  className={cn(
                    'num text-right text-sm font-medium',
                    row.edge > 0 ? 'text-positive' : 'text-negative',
                  )}
                >
                  {`${row.edge >= 0 ? '+' : ''}${(row.edge * 100).toFixed(1)}%`}
                </TableCell>
                <TableCell
                  className={cn(
                    'num text-right text-sm font-bold',
                    row.ev > 0 ? 'text-positive' : 'text-negative',
                  )}
                >
                  {`${row.ev >= 0 ? '+' : ''}${row.ev.toFixed(2)}`}
                </TableCell>
                <TableCell className="text-right">
                  <span
                    className={cn(
                      'inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold',
                      isEvPositive && 'bg-positive/15 text-positive border border-positive/30',
                      isAvoid && 'bg-negative/15 text-negative border border-negative/30',
                      !isEvPositive && !isAvoid && 'bg-muted text-muted-foreground',
                    )}
                  >
                    <span aria-hidden>{verdict.icon}</span>
                    {verdict.label}
                  </span>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
