import { ArrowUpRight, Check, Lock, Minus, ShieldAlert } from 'lucide-react'
import Link from 'next/link'
import type { MarketRow } from '@/lib/betmind'
import { cn } from '@/lib/utils'

const VERDICT_META: Record<string, { className: string; label: string }> = {
  'EV+': { className: 'border border-positive/30 bg-positive/10 text-positive', label: 'POSITIVE_EV' },
  POSITIVE_EV: { className: 'border border-positive/30 bg-positive/10 text-positive', label: 'POSITIVE_EV' },
  MARGINAL: { className: 'border border-border/50 bg-surface text-muted-foreground', label: 'NO_VALUE' },
  'NO EDGE': { className: 'border border-border/50 bg-surface text-muted-foreground', label: 'NO_VALUE' },
  NO_VALUE: { className: 'border border-border/50 bg-surface text-muted-foreground', label: 'NO_VALUE' },
  AVOID: { className: 'border border-negative/30 bg-negative/10 text-negative', label: 'AVOID' },
}

const FREE_ROW_LIMIT = 2
const LOCKED_ROW_CLASSES = 'relative opacity-40 blur-[2px] pointer-events-none select-none'

interface MarketTableProps { rows: MarketRow[]; selectedKey?: string | null; onSelect?: (key: string) => void; isPro?: boolean }

function ProbabilityTrack({ row }: { row: MarketRow }) {
  const model = Math.max(0, Math.min(100, row.probability * 100))
  const implied = Math.max(0, Math.min(100, row.implied * 100))
  return <div className="mt-2 grid gap-1.5 text-[9px] font-mono text-muted-foreground"><div className="flex items-center gap-2"><span className="w-12 shrink-0">MODELO</span><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-inset"><div className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out" style={{ width: `${model}%` }} /></div><span className="w-10 text-right tabular-nums text-foreground">{model.toFixed(1)}%</span></div><div className="flex items-center gap-2"><span className="w-12 shrink-0">CASA</span><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-inset"><div className="h-full rounded-full bg-muted-foreground/60 transition-[width] duration-300 ease-out" style={{ width: `${implied}%` }} /></div><span className="w-10 text-right tabular-nums text-foreground">{row.implied ? `${implied.toFixed(1)}%` : 'N/D'}</span></div></div>
}

function Verdict({ row }: { row: MarketRow }) {
  const verdict = VERDICT_META[row.verdict] ?? VERDICT_META.NO_VALUE
  return <span className={cn('inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono text-[10px] font-bold', verdict.className)}>{row.verdict === 'EV+' ? <Check className="size-3" /> : row.verdict === 'AVOID' ? <ShieldAlert className="size-3" /> : <Minus className="size-3" />}{verdict.label}</span>
}

export function MarketTable({ rows, selectedKey, onSelect, isPro = true }: MarketTableProps) {
  const locked = !isPro && rows.length > FREE_ROW_LIMIT
  const visibleRows = locked ? rows.slice(0, FREE_ROW_LIMIT) : rows
  const lockedRows = locked ? rows.slice(FREE_ROW_LIMIT) : []

  const renderRow = (row: MarketRow) => {
    const isSelected = selectedKey === row.key
    return <button key={row.key} type="button" onClick={() => onSelect?.(row.key)} className={cn('grid w-full gap-3 px-4 py-3 text-left transition-[background-color,box-shadow] duration-180 ease-out hover:bg-surface/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary sm:grid-cols-[minmax(0,1.2fr)_minmax(220px,1fr)_90px_120px] sm:items-center sm:gap-4', row.verdict === 'EV+' && 'bg-positive/[0.04]', isSelected && 'bg-primary/[0.08] ring-1 ring-inset ring-primary/30', locked && LOCKED_ROW_CLASSES)}><span className="min-w-0"><span className="flex items-center gap-1.5 font-semibold text-foreground">{row.label} {row.verdict === 'EV+' && <ArrowUpRight className="size-3 text-positive" />}</span><span className="font-mono text-[10px] text-muted-foreground">Cuota {row.odds > 1 ? row.odds.toFixed(2) : 'N/D'}</span><span className="sm:hidden"><ProbabilityTrack row={row} /></span></span><span className="hidden sm:block"><ProbabilityTrack row={row} /></span><span className="flex items-center justify-between gap-2 sm:block sm:text-right"><span className={cn('font-mono font-bold tabular-nums', row.edge > 0 ? 'text-positive' : 'text-muted-foreground')}>{row.edge > 0 ? '+' : ''}{(row.edge * 100).toFixed(1)}%</span><span className="ml-2 font-mono text-[10px] tabular-nums text-muted-foreground">EV {row.ev > 0 ? '+' : ''}{(row.ev * 100).toFixed(1)}%</span></span><span className="justify-self-start sm:justify-self-end"><Verdict row={row} /></span></button>
  }

  return <div className="overflow-hidden rounded-xl border border-border/60 bg-card text-xs"><div className="hidden border-b border-border/50 bg-surface/40 px-4 py-2 text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground sm:grid sm:grid-cols-[minmax(0,1.2fr)_minmax(220px,1fr)_90px_120px] sm:gap-4"><span>Mercado</span><span>Modelo vs. casa</span><span className="text-right">Edge / EV</span><span className="text-right">Veredicto</span></div><div className="divide-y divide-border/40">{visibleRows.map(renderRow)}{lockedRows.length > 0 && <div className="relative"><div aria-hidden="true" className="pointer-events-none select-none opacity-40 blur-[2px]">{lockedRows.map(renderRow)}</div><div className="absolute inset-0 z-10 flex items-center justify-center bg-background/55 px-4 backdrop-blur-[1px]"><div className="flex flex-col items-center gap-3 rounded-2xl border border-brand/30 bg-surface/95 p-5 text-center shadow-xl shadow-black/25"><div className="flex size-10 items-center justify-center rounded-full border border-brand/30 bg-brand/10 text-brand"><Lock className="size-4" aria-hidden="true" /></div><Link href="/planes" className="inline-flex min-h-10 items-center justify-center rounded-lg bg-brand px-4 text-sm font-bold text-primary-foreground transition-[transform,opacity] duration-150 hover:opacity-90 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand">Mercados VIP: Desbloquear con PRO</Link></div></div></div>}</div>{!rows.length && <div className="px-4 py-8 text-center text-sm text-muted-foreground">No hay mercados para comparar todavía.</div>}</div>
}
