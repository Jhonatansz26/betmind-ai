'use client'

import * as React from 'react'
import { motion } from 'framer-motion'
import { toast } from 'sonner'
import {
  TrendingUp,
  Swords,
  Target,
  Star,
  Activity,
  Flame,
  Sparkles,
  CheckCircle2,
  XCircle,
  Bell,
  Copy,
  ShieldAlert,
  Zap,
  BarChart2,
  User,
} from 'lucide-react'

import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import {
  buildModel,
  marketRows,
  type Match,
  type MatchModel,
  type MarketRow,
  type Mode,
} from '@/lib/betmind'
import { fetchMatchPrediction, type EnrichedMatch } from '@/lib/api'
import { cn } from '@/lib/utils'
import { TeamLogo } from '@/components/ui/team-logo'

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type DetailTab = 'previa' | 'h2h' | 'arbitro'
type FormResult = 'V' | 'E' | 'D'

interface MarketConfig {
  label: string
  prob: number
}

interface MatchDetailData {
  confidenceScore: number
  riskLevel: string
  probableScore: string
  underOverLabel: string
  underOverProb: number
  aiSummaryPill: string
  additionalMarkets: {
    dobleOportunidad: MarketConfig[]
    dnb: MarketConfig[]
    golesEquipo: MarketConfig[]
  }
  betBuilder: EnrichedMatch['betBuilder']
  narrative: string
  signalStrength: number
  homeRecentForm: FormResult[]
  awayRecentForm: FormResult[]
  homeExpectedGoals: number
  awayExpectedGoals: number
  totalExpectedGoals: number
  cornersLine: string
  cornersProb: number
  cardsLine: string
  cardsFriction: string
  avgCards: string
  avgReds: string
  avgFouls: string
}

/* ------------------------------------------------------------------ */
/* Data builders                                                       */
/* ------------------------------------------------------------------ */

const EXPANDED_MARKET_GROUPS = [
  { group: 'dobleOportunidad' as const, keys: ['DOUBLE_1X', 'DOUBLE_X2', 'DOUBLE_12'] },
  { group: 'dnb' as const, keys: ['DNB_HOME', 'DNB_AWAY'] },
  { group: 'golesEquipo' as const, keys: ['HOME_OVER_0_5', 'HOME_OVER_1_5', 'AWAY_OVER_0_5', 'AWAY_OVER_1_5'] },
]

const MARKET_LABELS: Record<string, string> = {
  DOUBLE_1X: '1X', DOUBLE_X2: 'X2', DOUBLE_12: '12',
  DNB_HOME: 'Local DNB', DNB_AWAY: 'Visitante DNB',
  HOME_OVER_0_5: 'Local +0.5', HOME_OVER_1_5: 'Local +1.5',
  AWAY_OVER_0_5: 'Visitante +0.5', AWAY_OVER_1_5: 'Visitante +1.5',
}

function buildDetail(match: Match, enriched: EnrichedMatch | null, model: MatchModel): MatchDetailData {
  const over25 = model.over25
  const underOverLabel = over25 > 0.5 ? 'Más de 2.5' : 'Menos de 2.5'
  const underOverProb = over25 > 0.5 ? over25 * 100 : (1 - over25) * 100

  const signalMap: Record<string, number> = { STRONG: 3, MODERATE: 2, WEAK: 1 }
  const signalStrength = signalMap[match.signal] ?? 1

  const evAnalysis = enriched?.evAnalysis ?? []

  const additional = {
    dobleOportunidad: [] as MarketConfig[],
    dnb: [] as MarketConfig[],
    golesEquipo: [] as MarketConfig[],
  }

  for (const item of EXPANDED_MARKET_GROUPS) {
    for (const key of item.keys) {
      const ev = evAnalysis.find(e => e.market === key)
      if (ev && ev.probability > 0) {
        additional[item.group].push({
          label: MARKET_LABELS[key] ?? key,
          prob: parseFloat((ev.probability * 100).toFixed(1)),
        })
      }
    }
  }

  const cardsNarr = enriched?.tacticalAnalysis?.cards_narrative as Record<string, unknown> | null
  const cornersNarr = enriched?.tacticalAnalysis?.corners_narrative as Record<string, unknown> | null

  const cornersProbStr = cornersNarr?.over_probability
  const cornersProb = typeof cornersProbStr === 'number'
    ? cornersProbStr * 100
    : typeof cornersProbStr === 'string'
      ? parseFloat(cornersProbStr) * 100
      : 50

  const cardsFrictionStr = cardsNarr?.friction_level ?? cardsNarr?.tactical_summary
  const cardsFriction = typeof cardsFrictionStr === 'string' ? cardsFrictionStr : 'Media'

  return {
    confidenceScore: enriched?.confidenceScore ?? 0,
    riskLevel: enriched?.riskLevel ?? 'MEDIUM',
    probableScore: model.mostLikely?.score ?? '--',
    underOverLabel,
    underOverProb: parseFloat(underOverProb.toFixed(0)),
    aiSummaryPill: enriched?.tacticalHeadline ?? '',
    additionalMarkets: additional,
    betBuilder: enriched?.betBuilder ?? [],
    narrative: enriched?.tacticalNarrative ?? '',
    signalStrength,
    homeRecentForm: [],
    awayRecentForm: [],
    homeExpectedGoals: match.lambdaHome,
    awayExpectedGoals: match.lambdaAway,
    totalExpectedGoals: match.lambdaHome + match.lambdaAway,
    cornersLine: typeof cornersNarr?.line === 'number' ? String(cornersNarr.line) : '8.5',
    cornersProb: parseFloat(cornersProb.toFixed(0)),
    cardsLine: typeof cardsNarr?.line === 'number' ? String(cardsNarr.line) : '3.5',
    cardsFriction,
    avgCards: match.referee.yellows > 0 ? match.referee.yellows.toFixed(1) : '3.5',
    avgReds: match.referee.reds > 0 ? match.referee.reds.toFixed(1) : '0.2',
    avgFouls: match.referee.fouls > 0 ? match.referee.fouls.toFixed(0) : '26',
  }
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function sectionLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <h3 className={cn('text-[10px] font-bold text-subtle uppercase tracking-widest', className)}>
      {children}
    </h3>
  )
}

function EmptyCard({ icon, title, subtitle }: { icon?: React.ReactNode; title: string; subtitle: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      <div className="w-12 h-12 rounded-full bg-surface-raised border border-border flex items-center justify-center mb-3">
        {icon ?? <User size={18} className="text-subtle" />}
      </div>
      <p className="text-sm font-semibold text-foreground mb-1">{title}</p>
      <p className="text-xs text-subtle max-w-xs leading-relaxed">{subtitle}</p>
    </div>
  )
}

const RISK_COLORS: Record<string, string> = {
  LOW: 'bg-positive/15 text-positive border-positive/25',
  MEDIUM: 'bg-warning/15 text-warning border-warning/25',
  HIGH: 'bg-negative/15 text-negative border-negative/25',
}

const RISK_LABELS: Record<string, string> = {
  LOW: 'Riesgo Bajo', MEDIUM: 'Riesgo Medio', HIGH: 'Riesgo Alto',
}

const FORM_STYLES: Record<FormResult, { bg: string; text: string; border: string }> = {
  V: { bg: 'bg-positive/20', text: 'text-positive', border: 'border-positive/40' },
  E: { bg: 'bg-surface-raised/40', text: 'text-foreground/80', border: 'border-border/50' },
  D: { bg: 'bg-negative/15', text: 'text-negative', border: 'border-negative/30' },
}

function FormBubbles({ form }: { form: FormResult[] }) {
  if (form.length === 0) return <span className="text-[10px] text-subtle">Sin datos</span>
  return (
    <div className="flex gap-1.5">
      {form.map((r, i) => {
        const cfg = FORM_STYLES[r]
        return (
          <div
            key={i}
            className={cn('w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-black border', cfg.bg, cfg.text, cfg.border)}
          >
            {r}
          </div>
        )
      })}
    </div>
  )
}

const NARRATIVE_SECTIONS: { key: string; icon: string; label: string }[] = [
  { key: 'Goles:', icon: '⚽', label: 'Goles' },
  { key: 'Tarjetas:', icon: '🟨', label: 'Tarjetas' },
  { key: 'Corners:', icon: '📐', label: 'Corners' },
  { key: 'Resumen:', icon: '📋', label: 'Resumen' },
]

function stripLambdas(text: string): string {
  return text
    .replace(/\(λ[^)]*\)/g, '')
    .replace(/\([^)]*λ[^)]*\)/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function NarrativeBody({ text }: { text: string }) {
  const allKeys = NARRATIVE_SECTIONS.map(s => s.key)
  const regex = new RegExp(`(${allKeys.map(k => k.replace(':', '\\:')).join('|')})`, 'g')
  const rawParts = text.split(regex).filter(Boolean)

  const segments: { icon: string; label: string; content: string }[] = []
  let pendingKey: { icon: string; label: string } | null = null

  for (const part of rawParts) {
    const match = NARRATIVE_SECTIONS.find(s => s.key === part)
    if (match) {
      pendingKey = { icon: match.icon, label: match.label }
    } else if (pendingKey) {
      segments.push({ ...pendingKey, content: stripLambdas(part.trim()) })
      pendingKey = null
    } else {
      const cleaned = stripLambdas(part.trim())
      if (cleaned) {
        segments.push({ icon: '📋', label: 'Análisis', content: cleaned })
      }
    }
  }

  if (!segments.length) {
    return <p className="text-sm text-zinc-300 leading-relaxed">{stripLambdas(text)}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      {segments.map((seg, i) => (
        <div key={i} className="flex gap-3">
          <span className="shrink-0 text-base leading-none mt-0.5">{seg.icon}</span>
          <div>
            <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-0.5">{seg.label}</p>
            <p className="text-sm text-zinc-300 leading-relaxed">{seg.content}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Modal Header                                                        */
/* ------------------------------------------------------------------ */

function ModalHeader({ match, model }: { match: Match; model: MatchModel }) {
  const hw = model.home * 100
  const dw = model.draw * 100
  const aw = model.away * 100

  const isLive = match.status === 'IN_PLAY' || match.status === 'LIVE'
  const isPaused = match.status === 'PAUSED'
  const isFinished = match.status === 'FINISHED' || match.status === 'FT'
  const hasRealScore =
    match.score != null
    && match.score.length === 2
    && typeof match.score[0] === 'number'
    && typeof match.score[1] === 'number'
  const showScore = (isLive || isPaused || isFinished) && hasRealScore
  const hasElapsed = match.elapsed != null && match.elapsed > 0

  // Static color map — avoids dynamic class purging by Tailwind (P1.1)
  const PROB_COLORS = [
    { label: 'LOCAL',     className: 'text-primary' },
    { label: 'EMPATE',   className: 'text-foreground' },
    { label: 'VISITANTE', className: 'text-warning' },
  ] as const

  return (
    <div className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b border-border px-5 py-4 pr-12">
      {/* Hidden title for screen readers — includes both teams (P1.4) */}
      <DialogTitle className="sr-only">{match.home} vs {match.away}</DialogTitle>

      <div className="flex items-center gap-2 mb-4 text-[11px] text-subtle">
        <span aria-hidden>{match.flag}</span>
        <span>{match.league}</span>
        <span aria-hidden>·</span>
        <span>{match.time}</span>
        {isLive ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-positive/30 bg-positive/10 px-2 py-0.5 text-[10px] font-semibold text-positive">
            <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
            {hasElapsed ? `EN VIVO ${match.elapsed}'` : 'EN VIVO'}
          </span>
        ) : isPaused ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10px] font-semibold text-warning">
            <span className="size-1.5 rounded-full bg-warning" aria-hidden />
            PAUSADO
          </span>
        ) : isFinished ? (
          <span className="rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            FINALIZADO
          </span>
        ) : (
          <span className="rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            POR JUGAR
          </span>
        )}
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className="flex flex-1 items-center gap-3">
          <TeamLogo src={match.homeLogoUrl} teamName={match.home} teamId={match.homeTeamId} size={40} />
          {/* Visual name — DialogTitle sr-only above handles ARIA */}
          <span className="text-xl font-bold leading-tight text-foreground">
            {match.home}
          </span>
        </div>

        {/* Center: score or VS */}
        <div className="shrink-0 flex flex-col items-center">
          {showScore ? (
            <span className="text-2xl font-black tabular-nums text-foreground tracking-wide">
              {match.score![0]} – {match.score![1]}
            </span>
          ) : isFinished ? (
            <span className="text-xs text-subtle italic">Resultado pendiente</span>
          ) : (
            <span className="shrink-0 rounded-full border border-border bg-surface px-3 py-1 text-xs text-subtle">
              vs
            </span>
          )}
          {isLive && hasElapsed && (
            <span className="text-[10px] font-semibold text-subtle mt-1">
              {match.elapsed}&apos;
            </span>
          )}
        </div>

        <div className="flex flex-1 items-center justify-end gap-3 text-right">
          <span className="text-xl font-bold leading-tight text-foreground">
            {match.away}
          </span>
          <TeamLogo src={match.awayLogoUrl} teamName={match.away} teamId={match.awayTeamId} size={40} />
        </div>
      </div>

      {/* 1X2 probability quick bar — only when scheduled */}
      {!isLive && !isPaused && !isFinished && (
        <div className="grid grid-cols-3 gap-2">
          {PROB_COLORS.map(({ label, className: cls }, i) => {
            const val = i === 0 ? model.home : i === 1 ? model.draw : model.away
            return (
              <div
                key={label}
                className="flex flex-col items-center gap-0.5 rounded-lg border border-border/30 bg-surface/40 py-2"
              >
                <span className="text-[10px] font-semibold tracking-widest text-subtle uppercase">
                  {label}
                </span>
                <span className={cn('num text-base font-bold', cls)}>
                  {(val * 100).toFixed(1)}%
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* ConfidenceBar                                                       */
/* ------------------------------------------------------------------ */

function ModalConfidenceBar({ detail }: { detail: MatchDetailData }) {
  const riskColor = RISK_COLORS[detail.riskLevel] ?? RISK_COLORS.MEDIUM
  const riskLabel = RISK_LABELS[detail.riskLevel] ?? RISK_LABELS.MEDIUM

  if (detail.confidenceScore <= 0 && !detail.probableScore && !detail.aiSummaryPill) return null

  return (
    <div className="border-b border-border px-5 py-4">
      {detail.confidenceScore > 0 && (
        <div className="flex items-center gap-3 mb-3">
          <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider shrink-0">Confianza IA</span>
          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary to-primary/60 transition-all"
              style={{ width: `${detail.confidenceScore}%` }}
            />
          </div>
          <span className="text-[11px] font-bold text-foreground tabular-nums shrink-0">{detail.confidenceScore}/100</span>
          <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-md border shrink-0', riskColor)}>
            {riskLabel}
          </span>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {detail.probableScore !== '--' && (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-primary bg-primary/10 border border-primary/20 rounded-full px-3 py-1">
            <BarChart2 size={10} />
            Marcador probable: {detail.probableScore}
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-warning bg-warning/10 border border-warning/20 rounded-full px-3 py-1">
          <Flame size={10} />
          {detail.underOverLabel} {'—'} {detail.underOverProb}%
        </span>
        {detail.aiSummaryPill && (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground bg-muted border border-border rounded-full px-3 py-1">
            <Sparkles size={10} className="text-pink-400" />
            {detail.aiSummaryPill}
          </span>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* EVTable                                                             */
/* ------------------------------------------------------------------ */

function ModalEVTable({ rows, match }: { rows: MarketRow[]; match: Match }) {
  const best = React.useMemo(() => {
    const sorted = [...rows].sort((a, b) => b.edge - a.edge)
    return sorted[0] && sorted[0].edge >= 0.03 ? sorted[0] : null
  }, [rows])
  const [selectedMarket, setSelectedMarket] = React.useState<string | null>(() => best?.key ?? null)
  const [mode, setMode] = React.useState<Mode>('EDGE')
  const [saved, setSaved] = React.useState(false)

  const modeMeta: Record<Mode, { label: string; border: string; bg: string; accent: string }> = {
    EDGE:   { label: 'Modo Edge', border: 'border-indigo-500/40', bg: 'bg-indigo-500/15', accent: 'text-indigo-300' },
    VALUE:  { label: 'Modo Value', border: 'border-amber-500/40', bg: 'bg-amber-500/15', accent: 'text-amber-300' },
    BOLD:   { label: 'Modo Bold', border: 'border-rose-500/40', bg: 'bg-rose-500/15', accent: 'text-rose-300' },
  }

  const selectable = rows.filter(r => r.edge >= 0.03)

  return (
    <div className="flex flex-col gap-4">
      {best && (
        <div className="rounded-xl bg-positive/5 border border-positive/20 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 min-w-0">
              <span className="shrink-0 mt-0.5 text-[10px] font-black text-positive bg-positive/15 border border-positive/25 rounded-md px-1.5 py-0.5">EV+</span>
              <div>
                <p className="text-sm font-bold text-foreground">
                  {best.label}
                  <span className="text-subtle font-normal ml-2">+{(best.edge * 100).toFixed(1)}% edge</span>
                  <span className="text-subtle font-normal ml-1">{'·'} Cuota {best.odds.toFixed(2)}</span>
                </p>
                <p className="text-xs text-positive mt-0.5">Edge positivo sobre la probabilidad implícita del mercado</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSaved(s => !s)}
              className={cn(
                'shrink-0 flex items-center gap-1.5 text-xs font-bold px-3 py-2 rounded-lg border transition-all focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
                saved
                  ? 'bg-warning/15 border-warning/30 text-warning'
                  : 'bg-muted border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
              )}
            >
              <Star size={12} className={saved ? 'fill-warning text-warning' : ''} />
              {saved ? 'Guardado' : 'Guardar en mi Boleto'}
            </button>
          </div>
        </div>
      )}

      <div className="bg-surface border border-border rounded-xl overflow-hidden ring-1 ring-white/5">
        <div className="px-4 pt-4 pb-2">
          {sectionLabel({ children: 'Análisis de Valor Esperado (+EV)' })}
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-4 py-2 text-subtle font-semibold">Mercado</th>
              <th className="text-right px-3 py-2 text-subtle font-semibold">Prob.</th>
              <th className="text-right px-3 py-2 text-subtle font-semibold">Edge</th>
              <th className="text-right px-4 py-2 text-subtle font-semibold">Veredicto</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.key}
                onClick={() => setSelectedMarket(row.key)}
                className={cn(
                  'border-b border-border/50 last:border-0 cursor-pointer transition-colors',
                  row.verdict === 'EV+' && 'bg-positive/5 hover:bg-positive/10',
                  row.verdict !== 'EV+' && 'hover:bg-surface-raised',
                  selectedMarket === row.key && 'ring-1 ring-inset ring-primary/30 bg-primary/5'
                )}
              >
                <td className={cn("px-4 py-3", selectedMarket === row.key ? "font-semibold text-foreground" : "font-medium text-foreground/60")}>{row.label}</td>
                <td className="px-3 py-3 text-right tabular-nums text-muted-foreground">{(row.probability * 100).toFixed(1)}%</td>
                <td className={cn('px-3 py-3 text-right tabular-nums font-bold', row.edge > 0 ? 'text-positive' : 'text-negative')}>
                  {row.edge > 0 ? '+' : ''}{(row.edge * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-right">
                  {row.verdict === 'EV+' ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-black text-positive bg-positive/10 border border-positive/20 rounded-md px-1.5 py-0.5">
                      <CheckCircle2 size={9} /> EV+
                    </span>
                  ) : row.verdict === 'AVOID' ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-black text-negative bg-negative/10 border border-negative/20 rounded-md px-1.5 py-0.5">
                      <XCircle size={9} /> AVOID
                    </span>
                  ) : (
                    <span className="text-[10px] text-subtle">{row.verdict}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-surface border border-border rounded-xl px-5 py-4 ring-1 ring-white/5">
        {sectionLabel({ children: 'Añadir al Boleto', className: 'mb-3' })}
        {selectedMarket && (() => {
          const row = rows.find(r => r.key === selectedMarket)
          if (!row) return null
          return (
            <div className="flex items-center gap-3 bg-surface-raised/50 border border-border rounded-lg px-3 py-2.5 mb-3">
              <div className="w-4 h-4 rounded-full bg-primary border-2 border-primary/60 shrink-0" />
              <span className="text-sm font-semibold text-foreground flex-1">{row.label}</span>
              <span className="text-sm font-bold text-foreground/80 tabular-nums">{row.odds.toFixed(2)}</span>
              <span className={cn('text-xs font-bold', row.edge > 0 ? 'text-positive' : 'text-negative')}>
                {row.edge > 0 ? '+' : ''}{(row.edge * 100).toFixed(1)}%
              </span>
            </div>
          )
        })()}
        <div className="flex gap-2 mb-3">
          {(['EDGE', 'VALUE', 'BOLD'] as Mode[]).map(m => {
            const meta = modeMeta[m]
            return (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={cn(
                  'flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border transition-all',
                  mode === m
                    ? cn(meta.bg, meta.border, meta.accent)
                    : 'bg-muted/60 border-border text-subtle hover:text-foreground'
                )}
              >
                {m === 'EDGE' && <Zap size={10} />}
                {m === 'VALUE' && <Star size={10} />}
                {m === 'BOLD' && <Flame size={10} />}
                {meta.label}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          disabled={!selectedMarket || !selectable.some(r => r.key === selectedMarket)}
          onClick={() => {
            const row = rows.find(r => r.key === selectedMarket)
            toast.success('Añadido al boleto', {
              description: `${row?.label} · ${match.home} vs ${match.away} · modo ${mode}`,
            })
          }}
          className="w-full bg-primary hover:bg-primary/90 disabled:bg-muted disabled:text-subtle text-primary-foreground font-bold text-sm py-2.5 rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          Añadir al Boleto
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* AdditionalMarkets                                                    */
/* ------------------------------------------------------------------ */

function ModalAdditionalMarkets({ detail }: { detail: MatchDetailData }) {
  const { additionalMarkets: am } = detail
  const hasAny = am.dobleOportunidad.length > 0 || am.dnb.length > 0 || am.golesEquipo.length > 0
  if (!hasAny) return null

  return (
    <div className="bg-surface border border-border rounded-xl px-5 py-4 ring-1 ring-white/5">
      {sectionLabel({ children: 'Mercados Adicionales', className: 'mb-3' })}
      <div className="grid grid-cols-2 gap-4">
        <div>
          {am.dobleOportunidad.length > 0 && (
            <>
              <p className="text-[10px] font-bold text-subtle uppercase tracking-wider mb-2">Doble Oportunidad</p>
              <div className="flex flex-col gap-1.5 mb-3">
                {am.dobleOportunidad.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-surface-raised/40 border border-border rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-foreground/80">{m.label}</span>
                    <span className="text-xs font-bold text-foreground tabular-nums">{m.prob}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
          {am.dnb.length > 0 && (
            <>
              <p className="text-[10px] font-bold text-subtle uppercase tracking-wider mb-2">Empate No Válido (DNB)</p>
              <div className="flex flex-col gap-1.5">
                {am.dnb.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-surface-raised/40 border border-border rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-foreground/80">{m.label}</span>
                    <span className="text-xs font-bold text-foreground tabular-nums">{m.prob}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
        <div>
          {am.golesEquipo.length > 0 && (
            <>
              <p className="text-[10px] font-bold text-subtle uppercase tracking-wider mb-2">Goles de Equipo</p>
              <div className="flex flex-col gap-1.5">
                {am.golesEquipo.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-surface-raised/40 border border-border rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-foreground/80">{m.label}</span>
                    <span className="text-xs font-bold text-foreground tabular-nums">{m.prob}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* TopScorers                                                          */
/* ------------------------------------------------------------------ */

function ModalTopScorers({ topScores }: { topScores: MatchModel['topScores'] }) {
  const valid = topScores.filter(s => s.probability > 0 && s.score !== '--')
  if (valid.length === 0) return null

  const maxProb = valid[0]?.probability ?? 1

  return (
    <div className="bg-surface border border-border rounded-xl px-5 py-4 ring-1 ring-white/5">
      {sectionLabel({ children: 'Top Marcadores Más Probables', className: 'mb-4' })}
      <div className="flex flex-col gap-3">
        {valid.map((s, i) => {
          const pct = parseFloat((s.probability * 100).toFixed(1))
          const barWidth = maxProb > 0 ? (s.probability / maxProb) * 100 : 0
          return (
            <div key={s.score} className="flex items-center gap-3">
              <div className={cn(
                'shrink-0 w-14 text-center font-black tabular-nums rounded-lg py-1.5 text-sm border',
                i === 0
                  ? 'bg-positive/10 border-positive/25 text-positive'
                  : 'bg-muted border-border text-foreground/70'
              )}>
                {s.score}
              </div>
              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all', i === 0 ? 'bg-positive' : 'bg-primary/60')}
                  style={{ width: `${barWidth}%` }}
                />
              </div>
              <div className="shrink-0 flex items-center gap-2">
                <span className={cn('text-xs font-bold tabular-nums w-10 text-right', i === 0 ? 'text-positive' : 'text-muted-foreground')}>
                  {pct}%
                </span>
                {i === 0 && (
                  <span className="text-[10px] font-black text-positive bg-positive/10 border border-positive/25 rounded-md px-1.5 py-0.5 whitespace-nowrap">
                    Más probable
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* ModelProbabilities (comparison bars)                                 */
/* ------------------------------------------------------------------ */

function ModalModelProbabilities({
  match,
  model,
  enriched,
}: {
  match: Match
  model: MatchModel
  enriched: EnrichedMatch | null
}) {
  const prob = enriched?.probabilities
  const rows = [
    { label: 'Victoria', home: model.home * 100, away: model.away * 100 },
    { label: 'Empate', home: model.draw * 100, away: model.draw * 100 },
    { label: 'Over 2.5', home: prob ? prob.over_2_5 * 100 : model.over25 * 100, away: prob ? prob.over_2_5 * 100 : model.over25 * 100 },
    { label: 'Ambos Anotan', home: model.btts * 100, away: model.btts * 100 },
  ]

  const homeShort = match.home.split(' ')[0]
  const awayShort = match.away.split(' ')[0]

  return (
    <div className="bg-surface border border-border rounded-xl px-5 py-4 ring-1 ring-white/5">
      <div className="grid grid-cols-3 items-center mb-3 text-[10px] font-bold uppercase tracking-wider">
        <span className="text-primary">{homeShort}</span>
        <span className="text-subtle text-center">Probabilidades</span>
        <span className="text-warning text-right">{awayShort}</span>
      </div>
      <div className="flex flex-col gap-3">
        {rows.map(row => (
          <div key={row.label}>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-foreground tabular-nums w-10 shrink-0">{row.home.toFixed(1)}%</span>
              <div className="flex-1 flex gap-px">
                <div className="flex-1 h-1.5 bg-muted rounded-l-full overflow-hidden">
                  <div className="h-full bg-primary rounded-l-full ml-auto" style={{ width: `${Math.min(row.home, 100)}%` }} />
                </div>
                <div className="flex-1 h-1.5 bg-muted rounded-r-full overflow-hidden">
                  <div className="h-full bg-warning rounded-r-full" style={{ width: `${Math.min(row.away, 100)}%` }} />
                </div>
              </div>
              <span className="text-xs font-bold text-foreground tabular-nums w-10 shrink-0 text-right">{row.away.toFixed(1)}%</span>
            </div>
            <p className="text-[10px] text-subtle text-center mt-0.5">{row.label}</p>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-subtle mt-3 pt-3 border-t border-border">
        Basado en el modelo cuantitativo Poisson calibrado con datos reales.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* CornersCards                                                        */
/* ------------------------------------------------------------------ */

function ModalCornersCards({ detail }: { detail: MatchDetailData }) {
  return (
    <div className="bg-surface border border-border rounded-xl px-5 py-4 ring-1 ring-white/5">
      {sectionLabel({ children: 'Corners y Tarjetas', className: 'mb-3' })}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-surface-raised/50 border border-border rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-sm bg-warning/20 border border-warning/30 flex items-center justify-center">
              <span className="text-[10px] font-black text-warning">C</span>
            </div>
            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Corners</span>
          </div>
          <p className="text-xl font-black text-foreground tabular-nums">+{detail.cornersLine}</p>
          <p className="text-xs text-subtle mt-0.5">Prob. Over: <span className="text-foreground/80 font-semibold">{detail.cornersProb}%</span></p>
        </div>
        <div className="bg-surface-raised/50 border border-border rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-sm bg-negative/20 border border-negative/30 flex items-center justify-center">
              <span className="text-[10px] font-black text-negative">T</span>
            </div>
            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Tarjetas</span>
          </div>
          <p className="text-xl font-black text-foreground tabular-nums">{detail.cardsLine}+</p>
          <p className="text-xs text-subtle mt-0.5">
            Fricción <span className={cn('font-semibold', detail.cardsFriction.includes('Alta') ? 'text-negative' : 'text-warning')}>{detail.cardsFriction}</span>
          </p>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* BetBuilder                                                          */
/* ------------------------------------------------------------------ */

const BET_BUILDER_CONFIG: Record<string, {
  label: string
  risk: string
  gradient: string
  border: string
  accent: string
  badge: string
  btn: string
}> = {
  conservador: {
    label: 'Conservador', risk: 'Bajo Riesgo',
    gradient: 'from-emerald-950/80 to-zinc-900/90', border: 'border-emerald-500/20',
    accent: 'text-emerald-400', badge: 'bg-emerald-500/15 border-emerald-500/25 text-emerald-300',
    btn: 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border-emerald-500/30',
  },
  moderado: {
    label: 'Moderado', risk: 'Riesgo Medio',
    gradient: 'from-amber-950/80 to-zinc-900/90', border: 'border-amber-500/20',
    accent: 'text-amber-400', badge: 'bg-amber-500/15 border-amber-500/25 text-amber-300',
    btn: 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border-amber-500/30',
  },
  cazador: {
    label: 'Cazador / +EV', risk: '+EV Máximo',
    gradient: 'from-rose-950/80 to-zinc-900/90', border: 'border-rose-500/20',
    accent: 'text-rose-400', badge: 'bg-rose-500/15 border-rose-500/25 text-rose-300',
    btn: 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/30',
  },
}

function mapProfile(profile: string): string {
  const p = profile.toLowerCase()
  if (p.includes('conserv') || p.includes('safe')) return 'conservador'
  if (p.includes('moder') || p.includes('balanced')) return 'moderado'
  if (p.includes('caz') || p.includes('ev') || p.includes('aggressive') || p.includes('bold')) return 'cazador'
  return 'moderado'
}

function ModalBetBuilder({ detail }: { detail: MatchDetailData }) {
  const profiles = detail.betBuilder
  if (!profiles || profiles.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        {sectionLabel({ children: 'Bet Builder Sugerido' })}
        <div className="flex items-center gap-1.5 text-[10px] bg-primary/10 backdrop-blur-md border border-primary/20 text-primary font-medium shadow-sm rounded-full px-2.5 py-1">
          <Sparkles size={9} className="text-muted-foreground" />
          IA {'\u00b7'} Groq
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {profiles.map(bb => {
          const type = mapProfile(bb.profile)
          const cfg = BET_BUILDER_CONFIG[type] ?? BET_BUILDER_CONFIG.moderado
          return (
            <div
              key={bb.profile}
              className={cn('rounded-xl border p-4 bg-gradient-to-b flex flex-col gap-3', cfg.gradient, cfg.border)}
            >
              <div className="flex items-center justify-between">
                <span className={cn('text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded-md border', cfg.badge)}>
                  {cfg.risk}
                </span>
                <span className="text-[10px] text-subtle font-semibold">Cuota comb.</span>
              </div>
              <div>
                <p className="text-[11px] font-bold text-foreground/70">{cfg.label}</p>
                <p className={cn('text-3xl font-black tabular-nums', cfg.accent)}>{bb.combined_odds.toFixed(2)}</p>
              </div>
              <div className="flex flex-col gap-1.5">
                {bb.selections.map(sel => (
                  <div key={sel.label} className="flex items-center gap-2">
                    <CheckCircle2 size={11} className={cfg.accent} />
                    <span className="text-xs text-foreground/70 flex-1 leading-tight">{sel.label}</span>
                    <span className="text-xs font-bold text-muted-foreground tabular-nums shrink-0">{sel.odds_estimate.toFixed(2)}</span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-[10px] text-subtle">Prob. comb. <span className="text-muted-foreground font-semibold">{(bb.combined_probability * 100).toFixed(0)}%</span></span>
                <button type="button" className={cn('flex items-center gap-1 text-[10px] font-bold px-2.5 py-1.5 rounded-lg border transition-all', cfg.btn)}>
                  <Copy size={9} />
                  Copiar al boleto {'\u2192'}
                </button>
              </div>
            </div>
          )
        })}
      </div>
      <p className="text-center text-[10px] text-subtle mt-3 flex items-center justify-center gap-1.5">
        <Sparkles size={9} />
        Modelo Poisson {'\u00b7'} calibrado con redes neuronales
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* PreviaTab (modal)                                                   */
/* ------------------------------------------------------------------ */

function ModalPreviaTab({
  match,
  enriched,
  model,
  rows,
  detail,
}: {
  match: Match
  enriched: EnrichedMatch | null
  model: MatchModel
  rows: MarketRow[]
  detail: MatchDetailData
}) {
  return (
    <div className="flex flex-col gap-5 p-5">
      <div className="grid grid-cols-[3fr_2fr] gap-5">
        <div className="flex flex-col gap-5 min-w-0">
          <ModalEVTable rows={rows} match={match} />
          <ModalAdditionalMarkets detail={detail} />
        </div>
        <div className="flex flex-col gap-4 min-w-0">
          <ModalModelProbabilities match={match} model={model} enriched={enriched} />
          <ModalTopScorers topScores={model.topScores} />
          <ModalCornersCards detail={detail} />
        </div>
      </div>

      {detail.betBuilder.length > 0 && (
        <div className="bg-surface border border-border rounded-xl px-5 py-4 ring-1 ring-white/5">
          <ModalBetBuilder detail={detail} />
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* H2HTab (modal)                                                      */
/* ------------------------------------------------------------------ */

function ModalH2HTab({
  match,
  enriched,
  detail,
}: {
  match: Match
  enriched: EnrichedMatch | null
  detail: MatchDetailData
}) {
  const hasLambdas = match.lambdaHome > 0 || match.lambdaAway > 0

  return (
    <div className="flex flex-col gap-4 p-5">
      <div className="flex justify-center">
        <div className="flex items-center gap-1.5 text-[11px] bg-primary/10 backdrop-blur-md border border-primary/20 text-primary font-medium shadow-sm rounded-full px-3 py-1">
          <Sparkles size={10} className="text-primary" />
          Análisis Táctico {'·'} Groq {'·'} Llama 3.3
        </div>
      </div>

      <div className="bg-surface border border-border rounded-xl overflow-hidden ring-1 ring-white/5">
        <div className="px-4 pt-4 pb-3">
          {sectionLabel({ children: 'Análisis Táctico & H2H' })}
        </div>

        <div className="px-4 pb-4 flex flex-col gap-4">
          <div className="bg-surface-raised/40 border border-border rounded-xl p-4">
            <p className="text-[10px] font-bold text-subtle uppercase tracking-widest mb-3">Forma Reciente {'·'} Últimos 5</p>
            <div className="flex items-center gap-3">
              <div className="flex flex-col gap-1.5 flex-1">
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">{match.home}</p>
                <FormBubbles form={detail.homeRecentForm} />
              </div>
              <span className="text-[10px] font-bold text-subtle uppercase">vs</span>
              <div className="flex flex-col gap-1.5 flex-1 items-end">
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider text-right">{match.away}</p>
                <FormBubbles form={detail.awayRecentForm} />
              </div>
            </div>
          </div>

          {hasLambdas && (
            <div className="bg-surface-raised/40 border border-border rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Modelo Cuantitativo</p>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-primary inline-block" /><span className="text-muted-foreground">{match.home.split(' ')[0]}</span></span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-warning inline-block" /><span className="text-muted-foreground">{match.away.split(' ')[0]}</span></span>
                </div>
              </div>
              <div className="flex flex-col gap-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-black tabular-nums text-primary">{detail.homeExpectedGoals.toFixed(2)}</span>
                    <span className="text-[10px] text-subtle">Goles Esperados</span>
                    <span className="text-sm font-black tabular-nums text-warning">{detail.awayExpectedGoals.toFixed(2)}</span>
                  </div>
                  <div className="flex h-2 gap-px">
                    <div className="flex-1 bg-muted rounded-l-full overflow-hidden">
                      <div className="h-full bg-primary rounded-l-full ml-auto" style={{ width: `${Math.min((detail.homeExpectedGoals / 3) * 100, 100)}%` }} />
                    </div>
                    <div className="flex-1 bg-muted rounded-r-full overflow-hidden">
                      <div className="h-full bg-warning rounded-r-full" style={{ width: `${Math.min((detail.awayExpectedGoals / 3) * 100, 100)}%` }} />
                    </div>
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-black tabular-nums text-primary">{detail.totalExpectedGoals.toFixed(2)} tot.</span>
                    <span className="text-[10px] text-subtle">Total Goles</span>
                    <span className="text-sm font-black tabular-nums text-warning">{detail.totalExpectedGoals.toFixed(2)} tot.</span>
                  </div>
                  <div className="flex h-2 gap-px">
                    <div className="flex-1 bg-muted rounded-l-full overflow-hidden">
                      <div className="h-full bg-primary/70 rounded-l-full ml-auto" style={{ width: `${Math.min((detail.totalExpectedGoals / 5) * 100, 100)}%` }} />
                    </div>
                    <div className="flex-1 bg-muted rounded-r-full overflow-hidden">
                      <div className="h-full bg-warning/70 rounded-r-full" style={{ width: `${Math.min((detail.totalExpectedGoals / 5) * 100, 100)}%` }} />
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                {detail.totalExpectedGoals < 2.2 && (
                  <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground bg-muted border border-border rounded-full px-2.5 py-1">
                    {'🔒'} Duelo cerrado
                  </span>
                )}
                {detail.homeExpectedGoals > detail.awayExpectedGoals + 0.5 && (
                  <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground bg-muted border border-border rounded-full px-2.5 py-1">
                    {'🏠'} Local dominante
                  </span>
                )}
              </div>
            </div>
          )}

          <div className="bg-surface-raised/40 border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-[10px] font-bold text-subtle uppercase tracking-widest">
                {detail.signalStrength === 3 ? 'Señal Fuerte' : detail.signalStrength === 2 ? 'Señal Media' : 'Señal Débil'}
              </p>
              <div className="flex gap-1">
                {[1, 2, 3].map(i => (
                  <div key={i} className={cn('w-2 h-2 rounded-full', i <= detail.signalStrength ? 'bg-primary' : 'bg-muted')} />
                ))}
              </div>
            </div>
            <p className="text-sm text-foreground/80 leading-relaxed">
              <span className="font-bold text-foreground">Resumen:</span> {detail.aiSummaryPill || `${match.home} vs ${match.away}`} {'—'} {match.league}
            </p>
          </div>
        </div>
      </div>

      {detail.narrative && (
        <div className="bg-surface/40 border border-border rounded-xl p-4">
          {sectionLabel({ children: 'Narrativa del Modelo', className: 'mb-3' })}
          <NarrativeBody text={detail.narrative} />
        </div>
      )}

      {!detail.narrative && enriched?.tacticalNarrative === '' && (
        <p className="rounded-xl border border-border bg-surface/30 px-4 py-3 text-[11px] text-subtle text-center">
          El análisis táctico detallado se genera 14 horas antes del inicio del partido.
        </p>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* ArbitroTab (modal)                                                  */
/* ------------------------------------------------------------------ */

function ModalArbitroTab({ match, detail }: { match: Match; detail: MatchDetailData }) {
  const [notified, setNotified] = React.useState(false)
  const hasReferee = match.referee.name && match.referee.name !== 'Por confirmar' && match.referee.strictness > 0

  return (
    <div className="flex flex-col gap-4 p-5">
      <div className="bg-surface border border-border rounded-xl overflow-hidden ring-1 ring-white/5">
        <div className="flex items-center justify-between px-4 pt-4 pb-3">
          {sectionLabel({ children: 'Perfil del Árbitro' })}
          <span className="text-[10px] text-subtle bg-muted border border-border rounded-md px-2 py-0.5">
            {hasReferee ? match.referee.name : 'Por confirmar'}
          </span>
        </div>
        <div className="px-4 pb-4">
          {hasReferee ? (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-surface-raised/50 border border-border rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-warning">{match.referee.yellows}</p>
                <p className="text-[10px] text-subtle mt-0.5">Amarillas prom.</p>
              </div>
              <div className="bg-surface-raised/50 border border-border rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-negative">{match.referee.reds}</p>
                <p className="text-[10px] text-subtle mt-0.5">Rojas prom.</p>
              </div>
              <div className="bg-surface-raised/50 border border-border rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-foreground">{match.referee.strictness}</p>
                <p className="text-[10px] text-subtle mt-0.5">Rigor (0{'-–'}100)</p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center py-8 text-center border border-dashed border-border rounded-xl">
              <div className="w-14 h-14 rounded-full bg-surface-raised border border-border flex items-center justify-center mb-4">
                <User size={22} className="text-subtle" />
              </div>
              <p className="text-sm font-bold text-foreground mb-1">{'\u00c1'}rbitro pendiente de confirmaci{'\u00f3'}n</p>
              <p className="text-xs text-subtle mb-4 leading-relaxed">
                Normalmente se confirma <span className="font-semibold text-muted-foreground">4{'\u20136 horas'}</span>
                <br />antes del partido
              </p>
              <button
                type="button"
                onClick={() => setNotified(s => !s)}
                className={cn(
                  'flex items-center gap-2 text-xs font-bold px-4 py-2 rounded-lg border transition-all focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
                  notified
                    ? 'bg-primary/15 border-primary/30 text-primary'
                    : 'bg-muted border-border text-foreground/80 hover:border-primary/40 hover:text-foreground'
                )}
              >
                <Bell size={12} className={notified ? 'text-primary' : ''} />
                {notified ? 'Notificación activada' : 'Notificarme cuando se confirme'}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="bg-surface border border-border rounded-xl px-5 py-4 ring-1 ring-white/5">
        {sectionLabel({ children: 'Contexto de la Liga', className: 'mb-3' })}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-surface-raised/50 border border-border rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-warning/20 border border-warning/30 flex items-center justify-center mx-auto mb-2">
              <div className="w-3 h-4 bg-warning rounded-sm" />
            </div>
            <p className="text-xl font-black tabular-nums text-foreground">{detail.avgCards}</p>
            <p className="text-[10px] text-subtle mt-0.5">Tarjetas prom. Liga</p>
            <p className="text-[10px] text-subtle/70">por partido</p>
          </div>
          <div className="bg-surface-raised/50 border border-border rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-negative/20 border border-negative/30 flex items-center justify-center mx-auto mb-2">
              <div className="w-3 h-4 bg-negative rounded-sm" />
            </div>
            <p className="text-xl font-black tabular-nums text-foreground">{detail.avgReds}</p>
            <p className="text-[10px] text-subtle mt-0.5">Rojas prom. Liga</p>
            <p className="text-[10px] text-subtle/70">por partido</p>
          </div>
          <div className="bg-surface-raised/50 border border-border rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-surface-raised border border-border flex items-center justify-center mx-auto mb-2">
              <ShieldAlert size={14} className="text-muted-foreground" />
            </div>
            <p className="text-xl font-black tabular-nums text-foreground">{detail.avgFouls}</p>
            <p className="text-[10px] text-subtle mt-0.5">Faltas prom. liga</p>
            <p className="text-[10px] text-subtle/70">por partido</p>
          </div>
        </div>
        <div className="flex items-start gap-2.5 mt-3 bg-warning/5 border border-warning/15 rounded-lg px-3 py-2.5">
          <span className="text-warning mt-0.5 shrink-0">{'\uD83D\uDCA1'}</span>
          <p className="text-xs text-muted-foreground leading-relaxed">
            <span className="font-bold text-foreground">Consejo:</span> En este mercado, el {'\u00e1'}rbitro puede mover las cuotas de tarjetas hasta un{' '}
            <span className="font-bold text-warning">15{'\u201325%'}</span>. Espera la confirmaci{'\u00f3'}n antes de apostar en mercados de disciplina.
          </p>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Main MatchModal                                                     */
/* ------------------------------------------------------------------ */

interface MatchModalProps {
  match: Match | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function MatchModal({ match, open, onOpenChange }: MatchModalProps) {
  const [activeTab, setActiveTab] = React.useState<DetailTab>('previa')
  const [enriched, setEnriched] = React.useState<EnrichedMatch | null>(null)

  React.useEffect(() => {
    if (open && match) {
      setActiveTab('previa')
      setEnriched(null)
      fetchMatchPrediction(match.id).then(setEnriched).catch(() => setEnriched(null))
    }
  }, [open, match?.id])

  const model = React.useMemo(
    () => (match ? buildModel(match.lambdaHome, match.lambdaAway) : null),
    [match],
  )
  const rows = React.useMemo(
    () => (match && model ? marketRows(match, model) : []),
    [match, model],
  )

  if (!match || !model) return null

  const detail = buildDetail(match, enriched, model)

  const tabs: { id: DetailTab; label: string; icon: React.ReactNode }[] = [
    { id: 'previa', label: 'Previa & Pronóstico', icon: <TrendingUp size={12} /> },
    { id: 'h2h', label: 'H2H & Táctico', icon: <Swords size={12} /> },
    { id: 'arbitro', label: 'Árbitro', icon: <Target size={12} /> },
  ]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] w-full overflow-y-auto border border-border/40 bg-background p-0 shadow-[0_8px_30px_rgb(0,0,0,0.8)] ring-1 ring-white/10 sm:max-w-[800px]">
        {/* Header */}
        <ModalHeader match={match} model={model} />

        {/* Confidence Bar */}
        <ModalConfidenceBar detail={detail} />

        {/* Tabs — same sticky bg as ModalHeader (P2.9) */}
        <div className="sticky top-0 z-20 bg-background/95 backdrop-blur-sm border-b border-border">
          <div className="flex items-center justify-center gap-6 px-5 py-3">
            {tabs.map(tab => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'relative flex items-center gap-2 text-xs font-semibold pb-2 transition-colors focus-visible:ring-0',
                  activeTab === tab.id
                    ? 'text-primary'
                    : 'text-subtle hover:text-muted-foreground'
                )}
              >
                {tab.icon}
                {tab.label.toUpperCase()}
                {activeTab === tab.id && (
                  <motion.div
                    layoutId="activeTabIndicator"
                    className="absolute bottom-[-1px] left-0 right-0 h-[2px] bg-primary rounded-full"
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'previa' && (
          <ModalPreviaTab match={match} enriched={enriched} model={model} rows={rows} detail={detail} />
        )}
        {activeTab === 'h2h' && (
          <ModalH2HTab match={match} enriched={enriched} detail={detail} />
        )}
        {activeTab === 'arbitro' && (
          <ModalArbitroTab match={match} detail={detail} />
        )}
      </DialogContent>
    </Dialog>
  )
}
