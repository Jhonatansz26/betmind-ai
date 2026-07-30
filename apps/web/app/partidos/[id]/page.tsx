'use client'

import * as React from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import {
  ArrowLeft,
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
import { toast } from 'sonner'

import {
  buildModel,
  marketRows,
  type Match,
  type MatchModel,
  type MarketRow,
  type Mode,
} from '@/lib/betmind'
import { fetchMatchPrediction, type EnrichedMatch } from '@/lib/api'
import { resolveLeague } from '@/lib/league-metadata'
import { cn } from '@/lib/utils'
import { TeamLogo } from '@/components/ui/team-logo'

/* ------------------------------------------------------------------ */
/* Local types                                                         */
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
  { group: 'dobleOportunidad', keys: ['DOUBLE_1X', 'DOUBLE_X2', 'DOUBLE_12'] },
  { group: 'dnb', keys: ['DNB_HOME', 'DNB_AWAY'] },
  { group: 'golesEquipo', keys: ['HOME_OVER_0_5', 'HOME_OVER_1_5', 'AWAY_OVER_0_5', 'AWAY_OVER_1_5'] },
] as const

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
    <p className={cn('text-[10px] font-bold text-zinc-500 uppercase tracking-widest', className)}>
      {children}
    </p>
  )
}

function EmptyCard({ icon, title, subtitle }: { icon?: React.ReactNode; title: string; subtitle: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      <div className="w-12 h-12 rounded-full bg-zinc-800/80 border border-zinc-700 flex items-center justify-center mb-3">
        {icon ?? <User size={18} className="text-zinc-500" />}
      </div>
      <p className="text-sm font-semibold text-zinc-300 mb-1">{title}</p>
      <p className="text-xs text-zinc-600 max-w-xs leading-relaxed">{subtitle}</p>
    </div>
  )
}

const RISK_COLORS: Record<string, string> = {
  LOW: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
  MEDIUM: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  HIGH: 'bg-rose-500/15 text-rose-400 border-rose-500/25',
}

const RISK_LABELS: Record<string, string> = {
  LOW: 'Riesgo Bajo', MEDIUM: 'Riesgo Medio', HIGH: 'Riesgo Alto',
}

const FORM_STYLES: Record<FormResult, { bg: string; text: string; border: string }> = {
  V: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/40' },
  E: { bg: 'bg-zinc-700/40', text: 'text-zinc-300', border: 'border-zinc-600/50' },
  D: { bg: 'bg-rose-500/15', text: 'text-rose-400', border: 'border-rose-500/30' },
}

function FormBubbles({ form }: { form: FormResult[] }) {
  if (form.length === 0) return <span className="text-[10px] text-zinc-600">Sin datos</span>
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
/* MatchHero                                                           */
/* ------------------------------------------------------------------ */

function MatchHero({ match, leagueMeta, model }: {
  match: Match
  leagueMeta: ReturnType<typeof resolveLeague>
  model: MatchModel
}) {
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

  const statusBadge = (
    <span className={cn(
      'ml-1 text-[10px] font-bold px-2 py-0.5 rounded-md',
      isLive
        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
        : isPaused
          ? 'bg-amber-500/15 text-amber-400 border border-amber-500/25'
          : isFinished
            ? 'bg-zinc-700/60 text-zinc-400 border border-zinc-600/50'
            : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
    )}>
      {isLive
        ? hasElapsed ? `EN VIVO ${match.elapsed}'` : 'EN VIVO'
        : isPaused
          ? 'PAUSADO'
          : isFinished
            ? 'FINALIZADO'
            : 'POR JUGAR'}
    </span>
  )

  return (
    <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-base">{leagueMeta.flag}</span>
        <span className="text-xs font-semibold text-zinc-400">{leagueMeta.name}</span>
        <span className="text-zinc-700 text-xs">·</span>
        <span className="text-xs text-zinc-500 tabular-nums">{match.time}</span>
        {statusBadge}
      </div>

      <div className="flex items-center gap-4 mb-5">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <TeamLogo src={match.homeLogoUrl} teamName={match.home} teamId={match.homeTeamId} size={40} />
          <span className="text-xl font-bold text-white truncate">{match.home}</span>
        </div>

        {/* Center: score or VS */}
        <div className="shrink-0 flex flex-col items-center">
          {showScore ? (
            <span className="text-2xl font-black tabular-nums text-white tracking-wide">
              {match.score![0]} – {match.score![1]}
            </span>
          ) : isFinished ? (
            <span className="text-xs text-zinc-500 italic">Resultado pendiente</span>
          ) : (
            <div className="w-10 h-10 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center">
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">vs</span>
            </div>
          )}
          {isLive && hasElapsed && (
            <span className="text-[9px] font-semibold text-zinc-500 mt-1">
              {match.elapsed}&apos;
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 flex-1 min-w-0 justify-end">
          <span className="text-xl font-bold text-white truncate text-right">{match.away}</span>
          <TeamLogo src={match.awayLogoUrl} teamName={match.away} teamId={match.awayTeamId} size={40} />
        </div>
      </div>

      {/* Probability boxes — only for upcoming matches */}
      {!isLive && !isPaused && !isFinished && (
        <>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Local</p>
              <p className="text-lg font-black tabular-nums text-indigo-400">{(model.home * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Empate</p>
              <p className="text-lg font-black tabular-nums text-zinc-200">{(model.draw * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Visitante</p>
              <p className="text-lg font-black tabular-nums text-amber-400">{(model.away * 100).toFixed(1)}%</p>
            </div>
          </div>

          <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
            <div className="bg-indigo-500 rounded-l-full" style={{ width: `${hw}%` }} />
            <div className="bg-zinc-500" style={{ width: `${dw}%` }} />
            <div className="bg-amber-500 rounded-r-full" style={{ width: `${aw}%` }} />
          </div>
        </>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* ConfidenceBar                                                       */
/* ------------------------------------------------------------------ */

function ConfidenceBar({ detail, model }: { detail: MatchDetailData; model: MatchModel }) {
  const riskColor = RISK_COLORS[detail.riskLevel] ?? RISK_COLORS.MEDIUM
  const riskLabel = RISK_LABELS[detail.riskLevel] ?? RISK_LABELS.MEDIUM

  return (
    <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl px-5 py-4">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider shrink-0">Confianza IA</span>
        <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-indigo-400 transition-all"
            style={{ width: `${detail.confidenceScore}%` }}
          />
        </div>
        <span className="text-[11px] font-bold text-zinc-300 tabular-nums shrink-0">{detail.confidenceScore}/100</span>
        <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-md border shrink-0', riskColor)}>
          {riskLabel}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {detail.probableScore !== '--' && (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 rounded-full px-3 py-1">
            <BarChart2 size={10} />
            Marcador probable: {detail.probableScore}
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-full px-3 py-1">
          <Flame size={10} />
          {detail.underOverLabel} — {detail.underOverProb}%
        </span>
        {detail.aiSummaryPill && (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-zinc-400 bg-zinc-800 border border-zinc-700 rounded-full px-3 py-1">
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

function EVTable({ rows, match, best }: { rows: MarketRow[]; match: Match; best: MarketRow | null }) {
  const [selectedMarket, setSelectedMarket] = React.useState<string | null>(() => best?.key ?? null)
  const [mode, setMode] = React.useState<Mode>('EDGE')
  const [saved, setSaved] = React.useState(false)

  const selectable = rows.filter(r => r.edge >= 0.03)

  const modeMeta: Record<Mode, { label: string; border: string; bg: string; accent: string }> = {
    EDGE:   { label: 'Modo Edge', border: 'border-indigo-500/40', bg: 'bg-indigo-500/15', accent: 'text-indigo-300' },
    VALUE:  { label: 'Modo Value', border: 'border-amber-500/40', bg: 'bg-amber-500/15', accent: 'text-amber-300' },
    BOLD:   { label: 'Modo Bold', border: 'border-rose-500/40', bg: 'bg-rose-500/15', accent: 'text-rose-300' },
  }

  return (
    <div className="flex flex-col gap-4">
      {/* EV+ Banner */}
      {best && (
        <div className="rounded-xl bg-emerald-500/5 border border-emerald-500/20 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 min-w-0">
              <span className="shrink-0 mt-0.5 text-[10px] font-black text-emerald-400 bg-emerald-500/15 border border-emerald-500/25 rounded-md px-1.5 py-0.5">EV+</span>
              <div>
                <p className="text-sm font-bold text-white">
                  {best.label}
                  <span className="text-zinc-500 font-normal ml-2">+{(best.edge * 100).toFixed(1)}% edge</span>
                  <span className="text-zinc-500 font-normal ml-1">· Cuota {best.odds.toFixed(2)}</span>
                </p>
                <p className="text-xs text-emerald-400 mt-0.5">Edge positivo sobre la probabilidad implícita del mercado</p>
              </div>
            </div>
            <button
              onClick={() => setSaved(s => !s)}
              className={cn(
                'shrink-0 flex items-center gap-1.5 text-xs font-bold px-3 py-2 rounded-lg border transition-all',
                saved
                  ? 'bg-amber-500/15 border-amber-500/30 text-amber-400'
                  : 'bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-indigo-500/50 hover:text-white'
              )}
            >
              <Star size={12} className={saved ? 'fill-amber-400 text-amber-400' : ''} />
              {saved ? 'Guardado' : 'Guardar en mi Boleto'}
            </button>
          </div>
        </div>
      )}

      {/* Trend pills */}
      <div>
        {sectionLabel({ children: 'Tendencias del Partido', className: 'mb-2' })}
        <div className="flex flex-wrap gap-2">
          {rows.find(r => r.key === 'over25' && r.verdict === 'EV+') && (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full px-3 py-1">
              <Flame size={10} />
              Más de 2.5 probable · {((rows.find(r => r.key === 'over25')?.probability ?? 0) * 100).toFixed(1)}%
            </span>
          )}
          {best && (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-3 py-1">
              <Activity size={10} />
              Edge alto detectado · +{(best.edge * 100).toFixed(1)}%
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl overflow-hidden">
        <div className="px-4 pt-4 pb-2">
          {sectionLabel({ children: 'Análisis de Valor Esperado (+EV)' })}
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800/80">
              <th className="text-left px-4 py-2 text-zinc-600 font-semibold">Mercado</th>
              <th className="text-right px-3 py-2 text-zinc-600 font-semibold">Prob.</th>
              <th className="text-right px-3 py-2 text-zinc-600 font-semibold">Edge</th>
              <th className="text-right px-4 py-2 text-zinc-600 font-semibold">Veredicto</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.key}
                onClick={() => setSelectedMarket(row.key)}
                className={cn(
                  'border-b border-zinc-800/50 last:border-0 cursor-pointer transition-colors',
                  row.verdict === 'EV+' && 'bg-emerald-500/5 hover:bg-emerald-500/10',
                  row.verdict !== 'EV+' && 'hover:bg-zinc-800/30',
                  selectedMarket === row.key && 'ring-1 ring-inset ring-indigo-500/30 bg-indigo-500/5'
                )}
              >
                <td className="px-4 py-3 font-semibold text-zinc-200">{row.label}</td>
                <td className="px-3 py-3 text-right tabular-nums text-zinc-400">{(row.probability * 100).toFixed(1)}%</td>
                <td className={cn('px-3 py-3 text-right tabular-nums font-bold', row.edge > 0 ? 'text-emerald-400' : 'text-rose-400')}>
                  {row.edge > 0 ? '+' : ''}{(row.edge * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-right">
                  {row.verdict === 'EV+' ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-black text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-md px-1.5 py-0.5">
                      <CheckCircle2 size={9} /> EV+
                    </span>
                  ) : row.verdict === 'AVOID' ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-black text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-md px-1.5 py-0.5">
                      <XCircle size={9} /> AVOID
                    </span>
                  ) : (
                    <span className="text-[10px] text-zinc-500">{row.verdict}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add to ticket */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4">
        {sectionLabel({ children: 'Añadir al Boleto', className: 'mb-3' })}
        {selectedMarket && (() => {
          const row = rows.find(r => r.key === selectedMarket)
          if (!row) return null
          const sel = selectable.find(r => r.key === selectedMarket)
          return (
            <div className="flex items-center gap-3 bg-zinc-800/50 border border-zinc-700/50 rounded-lg px-3 py-2.5 mb-3">
              <div className="w-4 h-4 rounded-full bg-indigo-500 border-2 border-indigo-400 shrink-0" />
              <span className="text-sm font-semibold text-zinc-200 flex-1">{row.label}</span>
              <span className="text-sm font-bold text-zinc-300 tabular-nums">{row.odds.toFixed(2)}</span>
              <span className={cn('text-xs font-bold', row.edge > 0 ? 'text-emerald-400' : 'text-rose-400')}>
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
                onClick={() => setMode(m)}
                className={cn(
                  'flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border transition-all',
                  mode === m
                    ? cn(meta.bg, meta.border, meta.accent)
                    : 'bg-zinc-800/60 border-zinc-700 text-zinc-500 hover:text-zinc-300'
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
          disabled={!selectedMarket || !selectable.some(r => r.key === selectedMarket)}
          onClick={() => {
            const row = rows.find(r => r.key === selectedMarket)
            toast.success('Añadido al boleto', {
              description: `${row?.label} · ${match.home} vs ${match.away} · modo ${mode}`,
            })
          }}
          className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white font-bold text-sm py-2.5 rounded-lg transition-colors"
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

function AdditionalMarkets({ detail }: { detail: MatchDetailData }) {
  const { additionalMarkets: am } = detail
  const hasAny = am.dobleOportunidad.length > 0 || am.dnb.length > 0 || am.golesEquipo.length > 0
  if (!hasAny) return null

  return (
    <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4">
      {sectionLabel({ children: 'Mercados Adicionales', className: 'mb-3' })}
      <div className="grid grid-cols-2 gap-4">
        <div>
          {am.dobleOportunidad.length > 0 && (
            <>
              <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-wider mb-2">Doble Oportunidad</p>
              <div className="flex flex-col gap-1.5 mb-3">
                {am.dobleOportunidad.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-zinc-800/40 border border-zinc-800 rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-zinc-300">{m.label}</span>
                    <span className="text-xs font-bold text-zinc-200 tabular-nums">{m.prob}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
          {am.dnb.length > 0 && (
            <>
              <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-wider mb-2">Empate No Válido (DNB)</p>
              <div className="flex flex-col gap-1.5">
                {am.dnb.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-zinc-800/40 border border-zinc-800 rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-zinc-300">{m.label}</span>
                    <span className="text-xs font-bold text-zinc-200 tabular-nums">{m.prob}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
        <div>
          {am.golesEquipo.length > 0 && (
            <>
              <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-wider mb-2">Goles de Equipo</p>
              <div className="flex flex-col gap-1.5">
                {am.golesEquipo.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-zinc-800/40 border border-zinc-800 rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-zinc-300">{m.label}</span>
                    <span className="text-xs font-bold text-zinc-200 tabular-nums">{m.prob}%</span>
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

function TopScorers({ topScores }: { topScores: MatchModel['topScores'] }) {
  const valid = topScores.filter(s => s.probability > 0 && s.score !== '--')
  if (valid.length === 0) return null

  const maxProb = valid[0]?.probability ?? 1

  return (
    <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4">
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
                  ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
                  : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-300'
              )}>
                {s.score}
              </div>
              <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all', i === 0 ? 'bg-emerald-500' : 'bg-indigo-500/60')}
                  style={{ width: `${barWidth}%` }}
                />
              </div>
              <div className="shrink-0 flex items-center gap-2">
                <span className={cn('text-xs font-bold tabular-nums w-10 text-right', i === 0 ? 'text-emerald-400' : 'text-zinc-400')}>
                  {pct}%
                </span>
                {i === 0 && (
                  <span className="text-[9px] font-black text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 rounded-md px-1.5 py-0.5 whitespace-nowrap">
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

function ModelProbabilities({
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
    {
      label: 'Victoria',
      home: model.home * 100,
      away: model.away * 100,
    },
    {
      label: 'Empate',
      home: model.draw * 100,
      away: model.draw * 100,
    },
    {
      label: 'Over 2.5',
      home: prob ? prob.over_2_5 * 100 : model.over25 * 100,
      away: prob ? prob.over_2_5 * 100 : model.over25 * 100,
    },
    {
      label: 'Ambos Anotan',
      home: model.btts * 100,
      away: model.btts * 100,
    },
  ]

  const homeShort = match.home.split(' ')[0]
  const awayShort = match.away.split(' ')[0]

  return (
    <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4">
      <div className="grid grid-cols-3 items-center mb-3 text-[10px] font-bold uppercase tracking-wider">
        <span className="text-indigo-400">{homeShort}</span>
        <span className="text-zinc-500 text-center">Probabilidades</span>
        <span className="text-amber-400 text-right">{awayShort}</span>
      </div>
      <div className="flex flex-col gap-3">
        {rows.map(row => (
          <div key={row.label}>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-zinc-200 tabular-nums w-10 shrink-0">{row.home.toFixed(1)}%</span>
              <div className="flex-1 flex gap-px">
                <div className="flex-1 h-1.5 bg-zinc-800 rounded-l-full overflow-hidden">
                  <div className="h-full bg-indigo-500 rounded-l-full ml-auto" style={{ width: `${Math.min(row.home, 100)}%` }} />
                </div>
                <div className="flex-1 h-1.5 bg-zinc-800 rounded-r-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-r-full" style={{ width: `${Math.min(row.away, 100)}%` }} />
                </div>
              </div>
              <span className="text-xs font-bold text-zinc-200 tabular-nums w-10 shrink-0 text-right">{row.away.toFixed(1)}%</span>
            </div>
            <p className="text-[10px] text-zinc-600 text-center mt-0.5">{row.label}</p>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-zinc-600 mt-3 pt-3 border-t border-zinc-800">
        Basado en el modelo cuantitativo Poisson calibrado con datos reales.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* CornersCards                                                        */
/* ------------------------------------------------------------------ */

function CornersCards({ detail }: { detail: MatchDetailData }) {
  return (
    <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4">
      {sectionLabel({ children: 'Corners y Tarjetas', className: 'mb-3' })}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-sm bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
              <span className="text-[9px] font-black text-amber-400">C</span>
            </div>
            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Corners</span>
          </div>
          <p className="text-xl font-black text-white tabular-nums">+{detail.cornersLine}</p>
          <p className="text-xs text-zinc-500 mt-0.5">Prob. Over: <span className="text-zinc-300 font-semibold">{detail.cornersProb}%</span></p>
        </div>
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-sm bg-rose-500/20 border border-rose-500/30 flex items-center justify-center">
              <span className="text-[9px] font-black text-rose-400">T</span>
            </div>
            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Tarjetas</span>
          </div>
          <p className="text-xl font-black text-white tabular-nums">{detail.cardsLine}+</p>
          <p className="text-xs text-zinc-500 mt-0.5">
            Fricción <span className={cn('font-semibold', detail.cardsFriction.includes('Alta') ? 'text-rose-400' : 'text-amber-400')}>{detail.cardsFriction}</span>
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
  dot: string
}> = {
  conservador: {
    label: 'Conservador',
    risk: 'Bajo Riesgo',
    gradient: 'from-emerald-950/80 to-zinc-900/90',
    border: 'border-emerald-500/20',
    accent: 'text-emerald-400',
    badge: 'bg-emerald-500/15 border-emerald-500/25 text-emerald-300',
    btn: 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border-emerald-500/30',
    dot: 'bg-emerald-500',
  },
  moderado: {
    label: 'Moderado',
    risk: 'Riesgo Medio',
    gradient: 'from-amber-950/80 to-zinc-900/90',
    border: 'border-amber-500/20',
    accent: 'text-amber-400',
    badge: 'bg-amber-500/15 border-amber-500/25 text-amber-300',
    btn: 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border-amber-500/30',
    dot: 'bg-amber-500',
  },
  cazador: {
    label: 'Cazador / +EV',
    risk: '+EV Máximo',
    gradient: 'from-rose-950/80 to-zinc-900/90',
    border: 'border-rose-500/20',
    accent: 'text-rose-400',
    badge: 'bg-rose-500/15 border-rose-500/25 text-rose-300',
    btn: 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/30',
    dot: 'bg-rose-500',
  },
}

function mapProfile(profile: string): string {
  const p = profile.toLowerCase()
  if (p.includes('conserv') || p.includes('safe')) return 'conservador'
  if (p.includes('moder') || p.includes('balanced')) return 'moderado'
  if (p.includes('caz') || p.includes('ev') || p.includes('aggressive') || p.includes('bold')) return 'cazador'
  return 'moderado'
}

function BetBuilder({ detail }: { detail: MatchDetailData }) {
  const profiles = detail.betBuilder
  if (!profiles || profiles.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        {sectionLabel({ children: 'Bet Builder Sugerido' })}
        <div className="flex items-center gap-1 text-[10px] text-zinc-600">
          <Sparkles size={9} className="text-zinc-500" />
          IA · Groq
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
                <span className="text-[10px] text-zinc-500 font-semibold">Cuota comb.</span>
              </div>
              <div>
                <p className="text-[11px] font-bold text-zinc-300">{cfg.label}</p>
                <p className={cn('text-3xl font-black tabular-nums', cfg.accent)}>{bb.combined_odds.toFixed(2)}</p>
              </div>
              <div className="flex flex-col gap-1.5">
                {bb.selections.map(sel => (
                  <div key={sel.label} className="flex items-center gap-2">
                    <CheckCircle2 size={11} className={cfg.accent} />
                    <span className="text-xs text-zinc-300 flex-1 leading-tight">{sel.label}</span>
                    <span className="text-xs font-bold text-zinc-400 tabular-nums shrink-0">{sel.odds_estimate.toFixed(2)}</span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-[10px] text-zinc-500">Prob. comb. <span className="text-zinc-400 font-semibold">{(bb.combined_probability * 100).toFixed(0)}%</span></span>
                <button className={cn('flex items-center gap-1 text-[10px] font-bold px-2.5 py-1.5 rounded-lg border transition-all', cfg.btn)}>
                  <Copy size={9} />
                  Copiar al boleto →
                </button>
              </div>
            </div>
          )
        })}
      </div>
      <p className="text-center text-[10px] text-zinc-700 mt-3 flex items-center justify-center gap-1.5">
        <Sparkles size={9} />
        Modelo Poisson · calibrado con redes neuronales
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* PreviaTab                                                           */
/* ------------------------------------------------------------------ */

function PreviaTab({
  match,
  enriched,
  model,
  rows,
  best,
  detail,
}: {
  match: Match
  enriched: EnrichedMatch | null
  model: MatchModel
  rows: MarketRow[]
  best: MarketRow | null
  detail: MatchDetailData
}) {
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-[3fr_2fr] gap-5">
        {/* Left */}
        <div className="flex flex-col gap-5 min-w-0">
          <EVTable rows={rows} match={match} best={best} />
          <AdditionalMarkets detail={detail} />
        </div>

        {/* Right */}
        <div className="flex flex-col gap-4 min-w-0">
          <ModelProbabilities match={match} model={model} enriched={enriched} />
          <TopScorers topScores={model.topScores} />
          <CornersCards detail={detail} />
        </div>
      </div>

      {/* Bet Builder full width */}
      {detail.betBuilder.length > 0 && (
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4">
          <BetBuilder detail={detail} />
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* H2HTab                                                              */
/* ------------------------------------------------------------------ */

function H2HTab({
  match,
  enriched,
  model,
  detail,
}: {
  match: Match
  enriched: EnrichedMatch | null
  model: MatchModel
  detail: MatchDetailData
}) {
  const hasLambdas = match.lambdaHome > 0 || match.lambdaAway > 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-center">
        <div className="flex items-center gap-1.5 text-[11px] text-zinc-500 bg-zinc-800/60 border border-zinc-700 rounded-full px-3 py-1">
          <Sparkles size={10} className="text-indigo-400" />
          Análisis Táctico · Groq · Llama 3.3
        </div>
      </div>

      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl overflow-hidden">
        <div className="px-4 pt-4 pb-3">
          {sectionLabel({ children: 'Análisis Táctico & H2H' })}
        </div>

        <div className="px-4 pb-4 flex flex-col gap-4">
          {/* Recent form */}
          <div className="bg-zinc-800/40 border border-zinc-800 rounded-xl p-4">
            <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3">Forma Reciente · Últimos 5</p>
            <div className="flex items-center gap-3">
              <div className="flex flex-col gap-1.5 flex-1">
                <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">{match.home}</p>
                <FormBubbles form={detail.homeRecentForm} />
              </div>
              <span className="text-[10px] font-bold text-zinc-600 uppercase">vs</span>
              <div className="flex flex-col gap-1.5 flex-1 items-end">
                <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider text-right">{match.away}</p>
                <FormBubbles form={detail.awayRecentForm} />
              </div>
            </div>
          </div>

          {/* Quantitative model */}
          {hasLambdas && (
            <div className="bg-zinc-800/40 border border-zinc-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Modelo Cuantitativo</p>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-indigo-500 inline-block" /><span className="text-zinc-400">{match.home.split(' ')[0]}</span></span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /><span className="text-zinc-400">{match.away.split(' ')[0]}</span></span>
                </div>
              </div>
              <div className="flex flex-col gap-3">
                {/* xG row */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-black tabular-nums text-indigo-400">{detail.homeExpectedGoals.toFixed(2)}</span>
                    <span className="text-[10px] text-zinc-500">Goles Esperados</span>
                    <span className="text-sm font-black tabular-nums text-amber-400">{detail.awayExpectedGoals.toFixed(2)}</span>
                  </div>
                  <div className="flex h-2 gap-px">
                    <div className="flex-1 bg-zinc-800 rounded-l-full overflow-hidden">
                      <div className="h-full bg-indigo-500 rounded-l-full ml-auto" style={{ width: `${Math.min((detail.homeExpectedGoals / 3) * 100, 100)}%` }} />
                    </div>
                    <div className="flex-1 bg-zinc-800 rounded-r-full overflow-hidden">
                      <div className="h-full bg-amber-500 rounded-r-full" style={{ width: `${Math.min((detail.awayExpectedGoals / 3) * 100, 100)}%` }} />
                    </div>
                  </div>
                </div>
                {/* Total goals row */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-black tabular-nums text-indigo-400">{detail.totalExpectedGoals.toFixed(2)} tot.</span>
                    <span className="text-[10px] text-zinc-500">Total Goles</span>
                    <span className="text-sm font-black tabular-nums text-amber-400">{detail.totalExpectedGoals.toFixed(2)} tot.</span>
                  </div>
                  <div className="flex h-2 gap-px">
                    <div className="flex-1 bg-zinc-800 rounded-l-full overflow-hidden">
                      <div className="h-full bg-indigo-500/70 rounded-l-full ml-auto" style={{ width: `${Math.min((detail.totalExpectedGoals / 5) * 100, 100)}%` }} />
                    </div>
                    <div className="flex-1 bg-zinc-800 rounded-r-full overflow-hidden">
                      <div className="h-full bg-amber-500/70 rounded-r-full" style={{ width: `${Math.min((detail.totalExpectedGoals / 5) * 100, 100)}%` }} />
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                {detail.totalExpectedGoals < 2.2 && (
                  <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-zinc-400 bg-zinc-800 border border-zinc-700 rounded-full px-2.5 py-1">
                    🔒 Duelo cerrado
                  </span>
                )}
                {detail.homeExpectedGoals > detail.awayExpectedGoals + 0.5 && (
                  <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-zinc-400 bg-zinc-800 border border-zinc-700 rounded-full px-2.5 py-1">
                    🏠 Local dominante
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Signal & narrative */}
          <div className="bg-zinc-800/40 border border-zinc-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                {detail.signalStrength === 3 ? 'Señal Fuerte' : detail.signalStrength === 2 ? 'Señal Media' : 'Señal Débil'}
              </p>
              <div className="flex gap-1">
                {[1, 2, 3].map(i => (
                  <div key={i} className={cn('w-2 h-2 rounded-full', i <= detail.signalStrength ? 'bg-indigo-400' : 'bg-zinc-700')} />
                ))}
              </div>
            </div>
            <p className="text-sm text-zinc-300 leading-relaxed">
              <span className="font-bold text-white">Resumen:</span> {detail.aiSummaryPill || `${match.home} vs ${match.away}`} — {match.league}
            </p>
          </div>
        </div>
      </div>

      {/* Narrative */}
      {detail.narrative && (
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-4">
          {sectionLabel({ children: 'Narrativa del Modelo', className: 'mb-3' })}
          <NarrativeBody text={detail.narrative} />
        </div>
      )}

      {!detail.narrative && enriched?.tacticalNarrative === '' && (
        <p className="rounded-xl border border-zinc-800 bg-zinc-900/30 px-4 py-3 text-[11px] text-zinc-500 text-center">
          El análisis táctico detallado se genera 14 horas antes del inicio del partido.
        </p>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* ArbitroTab                                                          */
/* ------------------------------------------------------------------ */

function ArbitroTab({ match, detail }: { match: Match; detail: MatchDetailData }) {
  const [notified, setNotified] = React.useState(false)
  const hasReferee = match.referee.name && match.referee.name !== 'Por confirmar' && match.referee.strictness > 0

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 pt-4 pb-3">
          {sectionLabel({ children: 'Perfil del Árbitro' })}
          <span className="text-[10px] text-zinc-500 bg-zinc-800 border border-zinc-700 rounded-md px-2 py-0.5">
            {hasReferee ? match.referee.name : 'Por confirmar'}
          </span>
        </div>
        <div className="px-4 pb-4">
          {hasReferee ? (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-amber-400">{match.referee.yellows}</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">Amarillas prom.</p>
              </div>
              <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-rose-400">{match.referee.reds}</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">Rojas prom.</p>
              </div>
              <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-white">{match.referee.strictness}</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">Rigor (0–100)</p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center py-8 text-center border border-dashed border-zinc-800 rounded-xl">
              <div className="w-14 h-14 rounded-full bg-zinc-800/80 border border-zinc-700 flex items-center justify-center mb-4">
                <User size={22} className="text-zinc-600" />
              </div>
              <p className="text-sm font-bold text-zinc-300 mb-1">Árbitro pendiente de confirmación</p>
              <p className="text-xs text-zinc-600 mb-4 leading-relaxed">
                Normalmente se confirma <span className="font-semibold text-zinc-400">4–6 horas</span>
                <br />antes del partido
              </p>
              <button
                onClick={() => setNotified(s => !s)}
                className={cn(
                  'flex items-center gap-2 text-xs font-bold px-4 py-2 rounded-lg border transition-all',
                  notified
                    ? 'bg-indigo-500/15 border-indigo-500/30 text-indigo-400'
                    : 'bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-indigo-500/40 hover:text-white'
                )}
              >
                <Bell size={12} className={notified ? 'text-indigo-400' : ''} />
                {notified ? 'Notificación activada' : 'Notificarme cuando se confirme'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* League context */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4">
        {sectionLabel({ children: 'Contexto de la Liga', className: 'mb-3' })}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-amber-500/20 border border-amber-500/30 flex items-center justify-center mx-auto mb-2">
              <div className="w-3 h-4 bg-amber-400 rounded-sm" />
            </div>
            <p className="text-xl font-black tabular-nums text-white">{detail.avgCards}</p>
            <p className="text-[10px] text-zinc-500 mt-0.5">Tarjetas prom. Liga</p>
            <p className="text-[10px] text-zinc-600">por partido</p>
          </div>
          <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-rose-500/20 border border-rose-500/30 flex items-center justify-center mx-auto mb-2">
              <div className="w-3 h-4 bg-rose-400 rounded-sm" />
            </div>
            <p className="text-xl font-black tabular-nums text-white">{detail.avgReds}</p>
            <p className="text-[10px] text-zinc-500 mt-0.5">Rojas prom. Liga</p>
            <p className="text-[10px] text-zinc-600">por partido</p>
          </div>
          <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-zinc-700/60 border border-zinc-600 flex items-center justify-center mx-auto mb-2">
              <ShieldAlert size={14} className="text-zinc-400" />
            </div>
            <p className="text-xl font-black tabular-nums text-white">{detail.avgFouls}</p>
            <p className="text-[10px] text-zinc-500 mt-0.5">Faltas prom. liga</p>
            <p className="text-[10px] text-zinc-600">por partido</p>
          </div>
        </div>
        <div className="flex items-start gap-2.5 mt-3 bg-amber-500/5 border border-amber-500/15 rounded-lg px-3 py-2.5">
          <span className="text-amber-400 mt-0.5 shrink-0">💡</span>
          <p className="text-xs text-zinc-400 leading-relaxed">
            <span className="font-bold text-zinc-300">Consejo:</span> En este mercado, el árbitro puede mover las cuotas de tarjetas hasta un{' '}
            <span className="font-bold text-amber-400">15–25%</span>. Espera la confirmación antes de apostar en mercados de disciplina.
          </p>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* MatchDetailContent                                                  */
/* ------------------------------------------------------------------ */

function MatchDetailContent({ match, enriched }: { match: Match; enriched?: EnrichedMatch | null }) {
  const [activeTab, setActiveTab] = React.useState<DetailTab>('previa')
  const model = React.useMemo(() => buildModel(match.lambdaHome, match.lambdaAway), [match])
  const rows  = React.useMemo(() => marketRows(match, model), [match, model])
  const best  = React.useMemo(() => {
    const sorted = [...rows].sort((a, b) => b.edge - a.edge)
    return sorted[0] && sorted[0].edge >= 0.03 ? sorted[0] : null
  }, [rows])
  const detail = React.useMemo(() => buildDetail(match, enriched ?? null, model), [match, enriched, model])
  const leagueMeta = resolveLeague(match.leagueExternalId, match.league)

  const tabs: { id: DetailTab; label: string; icon: React.ReactNode }[] = [
    { id: 'previa', label: 'Previa & Pronóstico', icon: <TrendingUp size={12} /> },
    { id: 'h2h', label: 'H2H & Táctico', icon: <Swords size={12} /> },
    { id: 'arbitro', label: 'Árbitro', icon: <Target size={12} /> },
  ]

  return (
    <div className="flex flex-col gap-4">
      <MatchHero match={match} leagueMeta={leagueMeta} model={model} />

      {detail.confidenceScore > 0 && (
        <ConfidenceBar detail={detail} model={model} />
      )}

      {/* Sticky tabs */}
      <div className="sticky top-14 z-20 bg-[#09090b]/95 backdrop-blur-sm py-3 -mx-6 px-6 border-b border-zinc-800/50">
        <div className="flex items-center justify-center gap-6">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 text-xs font-semibold pb-2 border-b-2 transition-all',
                activeTab === tab.id
                  ? 'text-indigo-400 border-indigo-400'
                  : 'text-zinc-500 border-transparent hover:text-zinc-300'
              )}
            >
              {tab.icon}
              {tab.label.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'previa' && (
        <PreviaTab match={match} enriched={enriched ?? null} model={model} rows={rows} best={best} detail={detail} />
      )}
      {activeTab === 'h2h' && (
        <H2HTab match={match} enriched={enriched ?? null} model={model} detail={detail} />
      )}
      {activeTab === 'arbitro' && (
        <ArbitroTab match={match} detail={detail} />
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Page Skeleton                                                       */
/* ------------------------------------------------------------------ */

function PageSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="h-40 animate-pulse rounded-xl bg-white/[0.04]" />
      <div className="h-10 animate-pulse rounded-lg bg-white/[0.03]" />
      <div className="h-56 animate-pulse rounded-xl bg-white/[0.04]" />
      <div className="h-24 animate-pulse rounded-xl bg-white/[0.03]" />
      <div className="h-72 animate-pulse rounded-xl bg-white/[0.04]" />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function PartidoDetailPage() {
  const params = useParams<{ id: string }>()
  const [match, setMatch]     = React.useState<Match | null>(null)
  const [enriched, setEnriched] = React.useState<EnrichedMatch | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError]     = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const result = await fetchMatchPrediction(params.id)
        if (!cancelled) {
          if (result) {
            setMatch(result)
            setEnriched(result)
          } else {
            setError(true)
          }
        }
      } catch {
        if (!cancelled) setError(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [params.id])

  return (
    <div className="min-h-svh bg-[#09090b]">
      <header className="sticky top-0 z-40 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-sm">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-3 px-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <ArrowLeft size={14} />
            Volver a Partidos
          </Link>
          {match && (
            <p className="ml-auto truncate text-sm font-bold text-zinc-300">
              {match.home} vs {match.away}
            </p>
          )}
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-5">
          {loading && <PageSkeleton />}
          {error && !loading && (
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-10 text-center">
              <p className="text-sm font-medium text-zinc-200">Partido no encontrado</p>
              <p className="mt-1 text-xs text-zinc-500">
                Es posible que el partido ya no esté disponible para hoy.
              </p>
              <Link
                href="/"
                className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-[#6366f1] hover:underline"
              >
                <ArrowLeft size={14} />
                Volver al inicio
              </Link>
            </div>
          )}
          {match && !loading && <MatchDetailContent match={match} enriched={enriched} />}
        </div>
      </div>
    </div>
  )
}
