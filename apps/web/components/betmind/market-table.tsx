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

const VERDICT_META: Record<MarketRow['verdict'], { icon: string; className: string }> = {
  'EV+': { icon: '✅', className: 'text-positive' },
  MARGINAL: { icon: '⚪', className: 'text-muted-foreground' },
  'NO EDGE': { icon: '❌', className: 'text-subtle' },
  AVOID: { icon: '❌', className: 'text-negative' },
}

export function MarketTable({ rows }: { rows: MarketRow[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <Table className="min-w-[560px]">
        <TableHeader>
          <TableRow className="border-border">
            <TableHead className="text-xs text-subtle">Market</TableHead>
            <TableHead className="text-right text-xs text-subtle">Our Prob.</TableHead>
            <TableHead className="text-right text-xs text-subtle">Odds</TableHead>
            <TableHead className="text-right text-xs text-subtle">Implied</TableHead>
            <TableHead className="text-right text-xs text-subtle">Edge</TableHead>
            <TableHead className="text-right text-xs text-subtle">EV</TableHead>
            <TableHead className="text-right text-xs text-subtle">Verdict</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const verdict = VERDICT_META[row.verdict]
            return (
              <TableRow key={row.key} className="border-border">
                <TableCell className="text-sm font-medium text-foreground">{row.label}</TableCell>
                <TableCell className="num text-right text-sm text-muted-foreground">
                  {`${(row.probability * 100).toFixed(1)}%`}
                </TableCell>
                <TableCell className="num text-right text-sm text-muted-foreground">
                  {row.odds.toFixed(2)}
                </TableCell>
                <TableCell className="num text-right text-sm text-muted-foreground">
                  {`${(row.implied * 100).toFixed(1)}%`}
                </TableCell>
                <TableCell
                  className={cn(
                    'num text-right text-sm',
                    row.edge > 0 ? 'text-positive' : 'text-negative',
                  )}
                >
                  {`${row.edge >= 0 ? '+' : ''}${(row.edge * 100).toFixed(1)}%`}
                </TableCell>
                <TableCell
                  className={cn(
                    'num text-right text-sm font-medium',
                    row.ev > 0 ? 'text-positive' : 'text-negative',
                  )}
                >
                  {`${row.ev >= 0 ? '+' : ''}${row.ev.toFixed(2)}`}
                </TableCell>
                <TableCell className={cn('text-right text-xs font-medium', verdict.className)}>
                  <span aria-hidden>{verdict.icon}</span> {row.verdict}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
