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
  BarChart3,
  ChevronDown,
  Clock3,
  User,
  Footprints,
  Goal,
  ClipboardList,
  LayoutList,
  Lock,
  Home,
  Lightbulb,
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
import { fetchMatchH2H, fetchMatchPrediction, type EnrichedMatch, type MatchH2HData } from '@/lib/api'
import { resolveLeague } from '@/lib/league-metadata'
import { formatMarketName } from '@/lib/formatMarketName'
import { cn } from '@/lib/utils'
import { TeamLogo } from '@/components/ui/team-logo'
import { MatchTabBar, type MatchTab } from '@/components/betmind/match-tab-bar'

/* ------------------------------------------------------------------ */
/* Local types                                                         */
/* ------------------------------------------------------------------ */

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

  const cornersEv = evAnalysis.find((e: { market: string }) => e.market === 'CORNERS_OVER_8_5')
  const cornersProb = cornersEv?.probability
    ? parseFloat((cornersEv.probability * 100).toFixed(0))
    : typeof cornersNarr?.our_probability === 'number'
      ? Math.round((cornersNarr.our_probability as number) * 100)
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
    cornersProb,
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
    <p className={cn('text-[10px] font-bold text-subtle tracking-[0.14em]', className)}>
      {children}
    </p>
  )
}

function EmptyCard({ icon, title, subtitle }: { icon?: React.ReactNode; title: string; subtitle: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      <div className="w-12 h-12 rounded-full bg-surface/80 border border-border flex items-center justify-center mb-3">
        {icon ?? <User size={18} className="text-subtle" />}
      </div>
      <p className="text-sm font-semibold text-foreground mb-1">{title}</p>
      <p className="text-xs text-muted-foreground max-w-xs leading-relaxed">{subtitle}</p>
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
  E: { bg: 'bg-muted/40', text: 'text-foreground', border: 'border-border/50' },
  D: { bg: 'bg-negative/15', text: 'text-negative', border: 'border-negative/30' },
}

function FormBubbles({ form }: { form: FormResult[] }) {
  if (form.length === 0) return <span className="text-[10px] text-muted-foreground">Sin datos</span>
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

function toFormResult(result: 'W' | 'D' | 'L'): FormResult {
  return result === 'W' ? 'V' : result === 'D' ? 'E' : 'D'
}

const NARRATIVE_SECTIONS: { key: string; icon: React.ElementType; label: string }[] = [
  { key: 'Goles:', icon: Goal, label: 'Goles' },
  { key: 'Tarjetas:', icon: Footprints, label: 'Tarjetas' },
  { key: 'Corners:', icon: LayoutList, label: 'Corners' },
  { key: 'Resumen:', icon: ClipboardList, label: 'Resumen' },
]

function stripLambdas(text: string): string {
  return text
    .replace(/(λ[^)]*)/g, '')
    .replace(/\([^)]*λ[^)]*\)/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function NarrativeBody({ text }: { text: string }) {
  const allKeys = NARRATIVE_SECTIONS.map(s => s.key)
  const regex = new RegExp(`(${allKeys.map(k => k.replace(':', '\\:')).join('|')})`, 'g')
  const rawParts = text.split(regex).filter(Boolean)

  const segments: { icon: React.ElementType; label: string; content: string }[] = []
  let pendingKey: { icon: React.ElementType; label: string } | null = null

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
        segments.push({ icon: ClipboardList, label: 'Análisis', content: cleaned })
      }
    }
  }

  if (!segments.length) {
    return <p className="text-sm text-foreground leading-relaxed">{stripLambdas(text)}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      {segments.map((seg, i) => {
        const Icon = seg.icon
        return (
          <div key={i} className="flex gap-3">
            <Icon size={12} className="shrink-0 mt-0.5 text-subtle" />
            <div>
              <p className="text-[10px] font-bold text-subtle uppercase tracking-wider mb-0.5">{seg.label}</p>
              <p className="text-sm text-foreground leading-relaxed">{seg.content}</p>
            </div>
          </div>
        )
      })}
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
        ? 'bg-positive/15 text-positive border border-positive/20'
        : isPaused
          ? 'bg-warning/15 text-warning border border-warning/25'
          : isFinished
            ? 'bg-muted text-subtle border border-border/50'
            : 'bg-surface text-subtle border border-border'
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
    <div className="bg-card border border-border rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-base">{leagueMeta.flag}</span>
        <span className="text-xs font-semibold text-subtle">{leagueMeta.name}</span>
        <span className="text-muted-foreground text-xs">·</span>
        <span className="text-xs text-subtle tabular-nums">{match.time}</span>
        {statusBadge}
      </div>

      <div className="flex items-center gap-4 mb-5">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <TeamLogo src={match.homeLogoUrl} teamName={match.home} teamId={match.homeTeamId} size={40} />
          <span className="text-xl font-bold text-foreground truncate">{match.home}</span>
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
            <div className="w-10 h-10 rounded-full bg-surface border border-border flex items-center justify-center">
              <span className="text-[10px] font-bold text-subtle uppercase tracking-widest">vs</span>
            </div>
          )}
          {isLive && hasElapsed && (
            <span className="text-[9px] font-semibold text-subtle mt-1">
              {match.elapsed}&apos;
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 flex-1 min-w-0 justify-end">
          <span className="text-xl font-bold text-foreground truncate text-right">{match.away}</span>
          <TeamLogo src={match.awayLogoUrl} teamName={match.away} teamId={match.awayTeamId} size={40} />
        </div>
      </div>

      {/* Probability boxes — only for upcoming matches */}
      {!isLive && !isPaused && !isFinished && (
        <>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
              <p className="text-[10px] font-semibold text-subtle uppercase tracking-wider mb-1.5">Local</p>
              <p className="text-lg font-black tabular-nums text-primary">{(model.home * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
              <p className="text-[10px] font-semibold text-subtle uppercase tracking-wider mb-1.5">Empate</p>
              <p className="text-lg font-black tabular-nums text-foreground">{(model.draw * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
              <p className="text-[10px] font-semibold text-subtle uppercase tracking-wider mb-1.5">Visitante</p>
              <p className="text-lg font-black tabular-nums text-warning">{(model.away * 100).toFixed(1)}%</p>
            </div>
          </div>

          <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
            <div className="bg-primary rounded-l-full" style={{ width: `${hw}%` }} />
            <div className="bg-muted" style={{ width: `${dw}%` }} />
            <div className="bg-warning rounded-r-full" style={{ width: `${aw}%` }} />
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
    <div className="bg-card border border-border rounded-2xl px-5 py-4">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-[11px] font-bold text-subtle uppercase tracking-wider shrink-0">Confianza IA</span>
        <div className="flex-1 h-2 bg-surface rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary to-primary/70 transition-all"
            style={{ width: `${detail.confidenceScore}%` }}
          />
        </div>
        <span className="text-[11px] font-bold text-foreground tabular-nums shrink-0">{detail.confidenceScore}/100</span>
        <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-md border shrink-0', riskColor)}>
          {riskLabel}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {detail.probableScore !== '--' && (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-primary/80 bg-primary/10 border border-primary/20 rounded-full px-3 py-1">
            <BarChart2 size={10} />
            Marcador probable: {detail.probableScore}
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-warning/80 bg-warning/10 border border-warning/20 rounded-full px-3 py-1">
          <Flame size={10} />
          {detail.underOverLabel} — {detail.underOverProb}%
        </span>
        {detail.aiSummaryPill && (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-subtle bg-surface border border-border rounded-full px-3 py-1">
            <Sparkles size={10} className="text-pink-400" />
            {detail.aiSummaryPill}
          </span>
        )}
      </div>
    </div>
  )
}

function SignalRail({ match, detail, enriched, marketEdge }: { match: Match; detail: MatchDetailData; enriched: EnrichedMatch | null; marketEdge: number }) {
  const oddsCount = Object.values(match.odds).filter((value) => value > 1).length
  const completeness = Math.round((enriched?.tacticalAnalysis?.data_completeness_score ?? 0) * 100)
  const marketOpen = marketEdge >= 0.03
  return (
    <div className="grid grid-cols-1 overflow-hidden rounded-2xl border border-primary/20 bg-primary/[0.06] sm:grid-cols-3">
      <div className="flex items-center gap-3 border-b border-primary/10 px-4 py-3 sm:border-b-0 sm:border-r"><Activity size={16} className="text-primary" aria-hidden="true" /><div><p className="text-[10px] tracking-[0.12em] text-subtle">Señal BetMind</p><p className="font-mono text-sm font-bold text-foreground">{detail.confidenceScore}/100</p></div></div>
      <div className="flex items-center gap-3 border-b border-primary/10 px-4 py-3 sm:border-b-0 sm:border-r"><Target size={16} className={marketOpen ? 'text-positive' : 'text-subtle'} aria-hidden="true" /><div><p className="text-[10px] tracking-[0.12em] text-subtle">Estado del mercado</p><p className={cn('font-mono text-sm font-bold', marketOpen ? 'text-positive' : 'text-subtle')}>{marketOpen ? 'OPORTUNIDAD +EV' : 'MERCADO AJUSTADO'}</p></div></div>
      <div className="flex items-center gap-3 px-4 py-3"><Clock3 size={16} className="text-warning" aria-hidden="true" /><div><p className="text-[10px] tracking-[0.12em] text-subtle">Cuotas · datos</p><p className="font-mono text-sm font-bold text-foreground">{oddsCount ? `${oddsCount} activas` : 'Sin cuotas'} · {completeness}%</p></div></div>
    </div>
  )
}

function CapitalProtectionPanel({ match, detail }: { match: Match; detail: MatchDetailData }) {
  const total = Math.max(0.01, detail.homeExpectedGoals + detail.awayExpectedGoals)
  const homeWidth = Math.min(100, (detail.homeExpectedGoals / total) * 100)
  return (
    <div className="rounded-2xl border border-warning/25 bg-[#11151B] p-5">
      <div className="rounded-xl border border-warning/20 bg-warning/[0.06] p-4"><p className="text-sm font-semibold text-warning">🛡️ Veredicto BetMind: Protege tu Capital</p><p className="mt-2 text-sm leading-6 text-foreground/80">Las cuotas 1X2 están perfectamente ajustadas por el mercado (0% EV). Explora los mercados secundarios a continuación.</p></div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
        <div><p className="text-[10px] tracking-[0.14em] text-subtle">Radar táctico · xG</p><div className="mt-3 flex items-end justify-between"><span className="font-mono text-lg font-bold text-primary">{detail.homeExpectedGoals.toFixed(2)}</span><span className="text-xs text-subtle">Goles esperados</span><span className="font-mono text-lg font-bold text-warning">{detail.awayExpectedGoals.toFixed(2)}</span></div><div className="mt-2 flex h-3 overflow-hidden rounded-full bg-[#252C35]"><div className="bg-primary" style={{ width: `${homeWidth}%` }} /><div className="bg-warning" style={{ width: `${100 - homeWidth}%` }} /></div><div className="mt-2 flex justify-between text-[10px] text-subtle"><span>{match.home}</span><span>{match.away}</span></div></div>
        <div className="grid grid-cols-2 gap-2"><div className="rounded-lg border border-[#252C35] bg-[#182029]/60 p-3"><p className="text-[10px] text-subtle">Córneres</p><p className="mt-1 text-sm font-semibold text-foreground">{detail.cornersLine} · {detail.cornersProb}%</p></div><div className="rounded-lg border border-[#252C35] bg-[#182029]/60 p-3"><p className="text-[10px] text-subtle">Fricción</p><p className="mt-1 text-sm font-semibold text-foreground">{detail.cardsFriction}</p></div><div className="col-span-2 rounded-lg border border-[#252C35] bg-[#182029]/60 p-3"><p className="text-[10px] text-subtle">Perfil del árbitro</p><p className="mt-1 text-sm font-semibold text-foreground">{match.refereeProfile?.name ?? 'Pendiente de confirmación'}</p></div></div>
      </div>
    </div>
  )
}

type QuantMarket = EnrichedMatch['evAnalysis'][number]

const MARKET_GROUPS = [
  { id: 'goals', label: '⚽ Goles & Resultado', match: (market: string) => !market.startsWith('CORNERS_') && !market.startsWith('CARDS_') && !market.startsWith('SHOTS_OT_') },
  { id: 'corners', label: '🚩 Córneres Totales', match: (market: string) => market.startsWith('CORNERS_') },
  { id: 'cards', label: '🟨 Tarjetas & Disciplina', match: (market: string) => market.startsWith('CARDS_') },
  { id: 'shots', label: '🎯 Remates a Puerta', match: (market: string) => market.startsWith('SHOTS_OT_') },
] as const

function MarketAccordion({ label, markets, defaultOpen = false }: { label: string; markets: QuantMarket[]; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(defaultOpen)
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex min-h-11 w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        <span className="text-sm font-semibold text-foreground">{label}</span><span className="flex items-center gap-2 font-mono text-xs text-subtle">{markets.length}<ChevronDown size={15} className={cn('transition-transform', open && 'rotate-180')} aria-hidden="true" /></span>
      </button>
      {open && (
        <div className="border-t border-[#252C35] p-2">
          <div className="hidden grid-cols-[minmax(0,1fr)_minmax(120px,0.8fr)_90px_110px] gap-3 px-3 py-2 text-[10px] tracking-[0.12em] text-subtle sm:grid">
            <span>Mercado</span><span>Probabilidad IA</span><span>Edge</span><span>Estado</span>
          </div>
          {markets.length === 0 ? <p className="px-3 py-4 text-sm text-subtle">Sin mercados disponibles.</p> : markets.map((market) => {
            const reliable = market.probability >= 0.70 && market.ev > 0
            const risky = market.probability < 0.35
            const probability = market.probability * 100
            return (
              <div key={market.market} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 rounded-lg px-3 py-3 even:bg-[#182029]/50 sm:grid-cols-[minmax(0,1fr)_minmax(120px,0.8fr)_90px_110px] sm:gap-3">
                <span className="min-w-0 truncate font-sans text-sm text-foreground">{formatMarketName(market.market)}</span>
                <div className="flex min-w-[112px] flex-col gap-1">
                  <span className="font-mono text-right text-sm font-semibold text-foreground sm:text-left">{probability.toFixed(1)}%</span>
                  <div className="h-1.5 overflow-hidden rounded-full bg-[#252C35]"><div className={cn('h-full rounded-full', market.ev > 0 ? 'bg-[#3DE3A5]' : 'bg-[#8577FF]')} style={{ width: `${Math.max(4, Math.min(100, probability))}%` }} /></div>
                </div>
                <span className={cn('font-mono text-right text-sm font-semibold', market.ev > 0 ? 'text-[#3DE3A5]' : 'text-subtle')}>{market.ev > 0 ? `+${(market.ev * 100).toFixed(1)}% EV` : `${(market.ev * 100).toFixed(1)}%`}</span>
                <span className={cn('col-span-2 justify-self-end text-[10px] font-semibold sm:col-span-1 sm:justify-self-start', reliable && 'rounded-md border border-[#3DE3A5]/25 bg-[#3DE3A5]/10 px-2 py-1 text-[#3DE3A5]', risky && 'rounded-md border border-negative/25 bg-negative/10 px-2 py-1 text-negative', !reliable && !risky && 'text-subtle')}>
                  {reliable ? '● +EV' : risky ? '● Riesgo Alto' : 'Neutro'}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function SignalCard({ market }: { market: QuantMarket }) {
  const probability = market.probability * 100
  const fairOdds = market.probability > 0 ? 1 / market.probability : 0
  const positiveValue = market.ev > 0
  return <div className="rounded-xl border border-[#252C35] bg-[#11151B] p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-sans text-sm font-semibold text-foreground">{formatMarketName(market.market)}</p><div className="mt-3 flex items-center gap-3"><div className="h-1.5 w-24 overflow-hidden rounded-full bg-[#252C35]"><div className={cn('h-full rounded-full', positiveValue ? 'bg-[#3DE3A5]' : 'bg-[#8577FF]')} style={{ width: `${Math.max(4, Math.min(100, probability))}%` }} /></div><span className="font-mono text-sm font-semibold text-foreground">{probability.toFixed(1)}%</span></div></div><span className={cn('rounded-md border px-2 py-1 font-mono text-xs font-bold', positiveValue ? 'border-[#3DE3A5]/25 bg-[#3DE3A5]/10 text-[#3DE3A5]' : 'border-[#8577FF]/25 bg-[#8577FF]/10 text-[#8577FF]')}>{positiveValue ? `+${(market.ev * 100).toFixed(1)}% EV` : 'Alta probabilidad'}</span></div><div className="mt-4 flex items-end justify-between gap-3 border-t border-[#252C35] pt-3"><div className="flex gap-5 text-xs"><div><p className="text-subtle">Cuota casa</p><p className="mt-1 font-mono font-semibold text-foreground">{market.odds > 1 ? market.odds.toFixed(2) : '—'}</p></div><div><p className="text-subtle">Cuota justa IA</p><p className="mt-1 font-mono font-semibold text-foreground">{fairOdds ? fairOdds.toFixed(2) : '—'}</p></div></div><button type="button" onClick={() => toast.success('Selección lista para añadir al boleto', { description: formatMarketName(market.market) })} className="inline-flex min-h-11 items-center rounded-lg bg-[#8577FF] px-3 text-xs font-semibold text-white transition-colors hover:bg-[#7568EF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8577FF]">Añadir al boleto</button></div></div>
}

function QuantMarkets({ enriched }: { enriched: EnrichedMatch | null }) {
  const markets = enriched?.evAnalysis ?? []
  const [showAll, setShowAll] = React.useState(false)
  const signals = [...markets].filter((market) => market.ev > 0 || market.probability > 0.65).sort((a, b) => (b.ev - a.ev) || (b.probability - a.probability)).slice(0, 5)
  return <div className="flex flex-col gap-4"><div className="flex items-end justify-between"><div><p className="text-[10px] tracking-[0.14em] text-subtle">Señales filtradas · 80/20</p><h2 className="mt-1 text-lg font-semibold text-foreground">Lo que merece atención</h2></div><span className="font-mono text-xs text-primary">{markets.length}/56 mercados</span></div>{signals.length > 0 ? <div className="grid gap-3 lg:grid-cols-2">{signals.map((market) => <SignalCard key={market.market} market={market} />)}</div> : <div className="rounded-xl border border-dashed border-[#252C35] bg-[#11151B] px-5 py-8 text-center text-sm text-subtle">No hay señales destacadas en este partido. El mercado está ajustado.</div>}<button type="button" onClick={() => setShowAll((value) => !value)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[#252C35] bg-[#11151B] px-4 text-sm font-semibold text-subtle transition-colors hover:border-[#8577FF]/50 hover:text-foreground">📂 {showAll ? 'Ocultar catálogo completo' : 'Explorar los 56 mercados completos (Modo Analista)'}</button>{showAll && <div className="flex flex-col gap-3 pt-2">{MARKET_GROUPS.map((group, index) => <MarketAccordion key={group.id} label={group.label} markets={markets.filter((market) => group.match(market.market))} defaultOpen={index === 0} />)}</div>}<p className="text-xs leading-5 text-subtle">Las señales priorizan valor o probabilidad relevante. Abre el catálogo completo cuando necesites investigar el detalle.</p></div>
}

function ScouterStats({ match }: { match: Match }) {
  const stats = match.advancedStats
  const hasStats = Boolean(stats && Object.values(stats).some((value) => typeof value === 'number'))
  if (!hasStats) return <div className="rounded-xl border border-dashed border-border bg-card px-5 py-8 text-center"><BarChart3 size={20} className="mx-auto text-primary" aria-hidden="true" /><p className="mt-3 text-sm font-semibold text-foreground">Datos en vivo al finalizar el partido</p><p className="mt-1 text-xs leading-5 text-subtle">Corners, remates, faltas y eventos aparecerán cuando termine el encuentro.</p></div>
  const items = [['Corners', stats?.home_corners, stats?.away_corners], ['Remates', stats?.home_shots, stats?.away_shots], ['A puerta', stats?.home_shots_on_target, stats?.away_shots_on_target], ['Faltas', stats?.home_fouls, stats?.away_fouls]] as const
  return <div className="rounded-xl border border-border bg-card p-4"><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold text-foreground">Datos Scouter</h2><span className="text-xs text-positive">Datos verificados</span></div><div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{items.map(([label, home, away]) => <div key={label} className="rounded-lg border border-border bg-surface-raised/50 p-3"><p className="text-[10px] text-subtle">{label}</p><p className="mt-1 font-mono text-sm font-semibold text-foreground">{home ?? '—'} <span className="text-subtle">·</span> {away ?? '—'}</p></div>)}</div>{match.refereeProfile && <p className="mt-3 text-xs text-subtle">Árbitro: <span className="text-foreground">{match.refereeProfile.name}</span> · {match.refereeProfile.yellow_cards_avg.toFixed(1)} amarillas por partido</p>}</div>
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
    EDGE:   { label: 'Modo Edge', border: 'border-primary/40', bg: 'bg-primary/15', accent: 'text-primary/80' },
    VALUE:  { label: 'Modo Value', border: 'border-warning/40', bg: 'bg-warning/15', accent: 'text-warning/80' },
    BOLD:   { label: 'Modo Bold', border: 'border-negative/40', bg: 'bg-negative/15', accent: 'text-negative/80' },
  }

  return (
    <div className="flex flex-col gap-4">
      {/* EV+ Banner */}
      {best && (
        <div className="rounded-xl bg-positive/5 border border-positive/20 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 min-w-0">
              <span className="shrink-0 mt-0.5 text-[10px] font-black text-positive bg-positive/15 border border-positive/25 rounded-md px-1.5 py-0.5">EV+</span>
              <div>
                <p className="text-sm font-bold text-foreground">
                  {best.label}
                  <span className="text-subtle font-normal ml-2">+{(best.edge * 100).toFixed(1)}% edge</span>
                  <span className="text-subtle font-normal ml-1">· Cuota {best.odds.toFixed(2)}</span>
                </p>
                <p className="text-xs text-positive mt-0.5">Edge positivo sobre la probabilidad implícita del mercado</p>
              </div>
            </div>
            <button
              onClick={() => setSaved(s => !s)}
              className={cn(
                'shrink-0 flex items-center gap-1.5 text-xs font-bold px-3 py-2 rounded-lg border transition-all',
                saved
                  ? 'bg-warning/15 border-warning/30 text-warning'
                  : 'bg-surface border-border text-foreground hover:border-primary/50 hover:text-foreground'
              )}
            >
              <Star size={12} className={saved ? 'fill-warning text-warning' : ''} />
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
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-warning bg-warning/10 border border-warning/20 rounded-full px-3 py-1">
              <Flame size={10} />
              Más de 2.5 probable · {((rows.find(r => r.key === 'over25')?.probability ?? 0) * 100).toFixed(1)}%
            </span>
          )}
          {best && (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-positive bg-positive/10 border border-positive/20 rounded-full px-3 py-1">
              <Activity size={10} />
              Edge alto detectado · +{(best.edge * 100).toFixed(1)}%
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 pt-4 pb-2">
          {sectionLabel({ children: 'Análisis de Valor Esperado (+EV)' })}
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-4 py-2 text-muted-foreground font-semibold">Mercado</th>
              <th className="text-right px-3 py-2 text-muted-foreground font-semibold">Prob.</th>
              <th className="text-right px-3 py-2 text-muted-foreground font-semibold">Edge</th>
              <th className="text-right px-4 py-2 text-muted-foreground font-semibold">Veredicto</th>
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
                  row.verdict !== 'EV+' && 'hover:bg-surface/30',
                  selectedMarket === row.key && 'ring-1 ring-inset ring-primary/30 bg-primary/5'
                )}
              >
                <td className="px-4 py-3 font-semibold text-foreground">{row.label}</td>
                <td className="px-3 py-3 text-right tabular-nums text-subtle">{(row.probability * 100).toFixed(1)}%</td>
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

      {/* Add to ticket */}
      <div className="bg-card border border-border rounded-xl p-4">
        {sectionLabel({ children: 'Añadir al Boleto', className: 'mb-3' })}
        {selectedMarket && (() => {
          const row = rows.find(r => r.key === selectedMarket)
          if (!row) return null
          const sel = selectable.find(r => r.key === selectedMarket)
          return (
            <div className="flex items-center gap-3 bg-surface/50 border border-border/50 rounded-lg px-3 py-2.5 mb-3">
              <div className="w-4 h-4 rounded-full bg-primary border-2 border-primary/70 shrink-0" />
              <span className="text-sm font-semibold text-foreground flex-1">{row.label}</span>
              <span className="text-sm font-bold text-foreground tabular-nums">{row.odds.toFixed(2)}</span>
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
                onClick={() => setMode(m)}
                className={cn(
                  'flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border transition-all',
                  mode === m
                    ? cn(meta.bg, meta.border, meta.accent)
                    : 'bg-surface/60 border-border text-subtle hover:text-foreground'
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
          className="w-full bg-primary hover:bg-primary/80 disabled:bg-muted disabled:text-subtle text-foreground font-bold text-sm py-2.5 rounded-lg transition-colors"
        >
          Añadir al Boleto
        </button>
      </div>
    </div>
  )
}

function PrimaryRecommendation({ match, best }: { match: Match; best: MarketRow | null }) {
  if (!best) return <div className="rounded-xl border border-dashed border-[#252C35] bg-[#11151B] p-5"><p className="text-[10px] tracking-[0.14em] text-subtle">Pronóstico principal</p><p className="mt-3 text-sm text-subtle">No hay una ventaja suficiente para recomendar una selección.</p></div>
  return <div className="rounded-xl border border-[#3DE3A5]/25 bg-[#11151B] p-5"><div className="flex items-start justify-between gap-4"><div><p className="text-[10px] tracking-[0.14em] text-[#3DE3A5]">Pronóstico principal · +EV máximo</p><h2 className="mt-2 text-xl font-semibold text-foreground">{best.label}</h2><p className="mt-1 text-sm text-subtle">Ventaja detectada sobre la probabilidad implícita del mercado.</p></div><span className="rounded-lg border border-[#3DE3A5]/25 bg-[#3DE3A5]/10 px-2.5 py-1 font-mono text-sm font-bold text-[#3DE3A5]">+{(best.edge * 100).toFixed(1)}%</span></div><div className="mt-5 flex items-end justify-between border-t border-[#252C35] pt-4"><div><p className="text-[10px] tracking-[0.12em] text-subtle">Cuota disponible</p><p className="mt-1 font-mono text-2xl font-bold text-foreground">{best.odds.toFixed(2)}</p></div><button type="button" onClick={() => toast.success('Selección lista para añadir al boleto', { description: `${best.label} · ${match.home} vs ${match.away}` })} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-[#8577FF] px-4 text-sm font-semibold text-white transition-colors hover:bg-[#7568ef] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8577FF]"><Zap size={15} aria-hidden="true" /> Añadir al boleto</button></div></div>
}

/* ------------------------------------------------------------------ */
/* AdditionalMarkets                                                    */
/* ------------------------------------------------------------------ */

function AdditionalMarkets({ detail }: { detail: MatchDetailData }) {
  const { additionalMarkets: am } = detail
  const hasAny = am.dobleOportunidad.length > 0 || am.dnb.length > 0 || am.golesEquipo.length > 0
  if (!hasAny) return null

  return (
    <div className="bg-card border border-border rounded-xl p-4">
      {sectionLabel({ children: 'Mercados Adicionales', className: 'mb-3' })}
      <div className="grid grid-cols-2 gap-4">
        <div>
          {am.dobleOportunidad.length > 0 && (
            <>
              <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2">Doble Oportunidad</p>
              <div className="flex flex-col gap-1.5 mb-3">
                {am.dobleOportunidad.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-surface/40 border border-border rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-foreground">{m.label}</span>
                    <span className="text-xs font-bold text-foreground tabular-nums">{m.prob}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
          {am.dnb.length > 0 && (
            <>
              <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2">Empate No Válido (DNB)</p>
              <div className="flex flex-col gap-1.5">
                {am.dnb.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-surface/40 border border-border rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-foreground">{m.label}</span>
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
              <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2">Goles de Equipo</p>
              <div className="flex flex-col gap-1.5">
                {am.golesEquipo.map(m => (
                  <div key={m.label} className="flex items-center justify-between bg-surface/40 border border-border rounded-lg px-2.5 py-1.5">
                    <span className="text-xs text-foreground">{m.label}</span>
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

function TopScorers({ topScores }: { topScores: MatchModel['topScores'] }) {
  const valid = topScores.filter(s => s.probability > 0 && s.score !== '--')
  if (valid.length === 0) return null

  const maxProb = valid[0]?.probability ?? 1

  return (
    <div className="bg-card border border-border rounded-xl p-4">
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
                  : 'bg-surface/60 border-border/60 text-foreground'
              )}>
                {s.score}
              </div>
              <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all', i === 0 ? 'bg-positive' : 'bg-primary/60')}
                  style={{ width: `${barWidth}%` }}
                />
              </div>
              <div className="shrink-0 flex items-center gap-2">
                <span className={cn('text-xs font-bold tabular-nums w-10 text-right', i === 0 ? 'text-positive' : 'text-subtle')}>
                  {pct}%
                </span>
                {i === 0 && (
                  <span className="text-[9px] font-black text-positive bg-positive/10 border border-positive/25 rounded-md px-1.5 py-0.5 whitespace-nowrap">
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
    <div className="bg-card border border-border rounded-xl p-4">
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
                <div className="flex-1 h-1.5 bg-surface rounded-l-full overflow-hidden">
                  <div className="h-full bg-primary rounded-l-full ml-auto" style={{ width: `${Math.min(row.home, 100)}%` }} />
                </div>
                <div className="flex-1 h-1.5 bg-surface rounded-r-full overflow-hidden">
                  <div className="h-full bg-warning rounded-r-full" style={{ width: `${Math.min(row.away, 100)}%` }} />
                </div>
              </div>
              <span className="text-xs font-bold text-foreground tabular-nums w-10 shrink-0 text-right">{row.away.toFixed(1)}%</span>
            </div>
            <p className="text-[10px] text-muted-foreground text-center mt-0.5">{row.label}</p>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-muted-foreground mt-3 pt-3 border-t border-border">
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
    <div className="bg-card border border-border rounded-xl p-4">
      {sectionLabel({ children: 'Corners y Tarjetas', className: 'mb-3' })}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-surface/50 border border-border/50 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-sm bg-warning/20 border border-warning/30 flex items-center justify-center">
              <span className="text-[9px] font-black text-warning">C</span>
            </div>
            <span className="text-[10px] font-bold text-subtle uppercase tracking-wider">Corners</span>
          </div>
          <p className="text-xl font-black text-foreground tabular-nums">+{detail.cornersLine}</p>
          <p className="text-xs text-subtle mt-0.5">Prob. Over: <span className="text-foreground font-semibold">{detail.cornersProb}%</span></p>
        </div>
        <div className="bg-surface/50 border border-border/50 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-sm bg-negative/20 border border-negative/30 flex items-center justify-center">
              <span className="text-[9px] font-black text-negative">T</span>
            </div>
            <span className="text-[10px] font-bold text-subtle uppercase tracking-wider">Tarjetas</span>
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
  dot: string
}> = {
  conservador: {
    label: 'Conservador',
    risk: 'Bajo Riesgo',
    gradient: 'from-emerald-950/80 to-zinc-900/90',
    border: 'border-positive/20',
    accent: 'text-positive',
    badge: 'bg-positive/15 border-positive/25 text-positive/80',
    btn: 'bg-positive/20 hover:bg-positive/30 text-positive/80 border-positive/30',
    dot: 'bg-positive',
  },
  moderado: {
    label: 'Moderado',
    risk: 'Riesgo Medio',
    gradient: 'from-amber-950/80 to-zinc-900/90',
    border: 'border-warning/20',
    accent: 'text-warning',
    badge: 'bg-warning/15 border-warning/25 text-warning/80',
    btn: 'bg-warning/20 hover:bg-warning/30 text-warning/80 border-warning/30',
    dot: 'bg-warning',
  },
  cazador: {
    label: 'Cazador / +EV',
    risk: '+EV Máximo',
    gradient: 'from-rose-950/80 to-zinc-900/90',
    border: 'border-negative/20',
    accent: 'text-negative',
    badge: 'bg-negative/15 border-negative/25 text-negative/80',
    btn: 'bg-negative/20 hover:bg-negative/30 text-negative/80 border-negative/30',
    dot: 'bg-negative',
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
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <Sparkles size={9} className="text-subtle" />
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
                <span className="text-[10px] text-subtle font-semibold">Cuota comb.</span>
              </div>
              <div>
                <p className="text-[11px] font-bold text-foreground">{cfg.label}</p>
                <p className={cn('text-3xl font-black tabular-nums', cfg.accent)}>{bb.combined_odds.toFixed(2)}</p>
              </div>
              <div className="flex flex-col gap-1.5">
                {bb.selections.map(sel => (
                  <div key={sel.label} className="flex items-center gap-2">
                    <CheckCircle2 size={11} className={cfg.accent} />
                    <span className="text-xs text-foreground flex-1 leading-tight">{sel.label}</span>
                    <span className="text-xs font-bold text-subtle tabular-nums shrink-0">{sel.odds_estimate.toFixed(2)}</span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-[10px] text-subtle">Prob. comb. <span className="text-subtle font-semibold">{(bb.combined_probability * 100).toFixed(0)}%</span></span>
                <button className={cn('flex items-center gap-1 text-[10px] font-bold px-2.5 py-1.5 rounded-lg border transition-all', cfg.btn)}>
                  <Copy size={9} />
                  Copiar al boleto →
                </button>
              </div>
            </div>
          )
        })}
      </div>
      <p className="text-center text-[10px] text-muted-foreground mt-3 flex items-center justify-center gap-1.5">
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
  const mainEdge = Math.max(...rows.filter((row) => row.key === 'home' || row.key === 'draw' || row.key === 'away').map((row) => row.edge), 0)
  return (
    <div className="flex flex-col gap-5">
       <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Left */}
         <div className="flex flex-col gap-5 min-w-0">
           {mainEdge >= 0.03 ? <PrimaryRecommendation match={match} best={best} /> : <CapitalProtectionPanel match={match} detail={detail} />}
        </div>

        {/* Right */}
        <div className="flex flex-col gap-4 min-w-0">
          <ModelProbabilities match={match} model={model} enriched={enriched} />
          <TopScorers topScores={model.topScores} />
          <CornersCards detail={detail} />
        </div>
      </div>

      <ScouterStats match={match} />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* H2HTab                                                              */
/* ------------------------------------------------------------------ */

function RadarChart({ home, away }: { home: number[]; away: number[] }) {
  const labels = ['Ataque', 'Defensa', 'Fricción', 'Córneres', 'Forma']
  const center = 100
  const radius = 68
  const point = (value: number, index: number) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / labels.length
    const distance = radius * Math.max(0, Math.min(100, value)) / 100
    return `${center + Math.cos(angle) * distance},${center + Math.sin(angle) * distance}`
  }
  const axis = (index: number) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / labels.length
    return `${center + Math.cos(angle) * radius},${center + Math.sin(angle) * radius}`
  }
  return <div className="flex flex-col items-center gap-3"><svg viewBox="0 0 200 200" className="h-64 w-64" role="img" aria-label="Comparativa táctica de cinco métricas"><polygon points={labels.map((_, index) => axis(index)).join(' ')} fill="none" stroke="var(--border)" strokeWidth="1" />{[25, 50, 75].map((scale) => <polygon key={scale} points={labels.map((_, index) => point(scale, index)).join(' ')} fill="none" stroke="var(--border)" strokeWidth="0.7" opacity="0.8" />)}{labels.map((label, index) => <line key={label} x1={center} y1={center} x2={axis(index).split(',')[0]} y2={axis(index).split(',')[1]} stroke="var(--border)" strokeWidth="0.7" />)}<polygon points={home.map((value, index) => point(value, index)).join(' ')} fill="rgba(133,119,255,0.20)" stroke="#8577FF" strokeWidth="2" /><polygon points={away.map((value, index) => point(value, index)).join(' ')} fill="rgba(61,227,165,0.12)" stroke="#3DE3A5" strokeWidth="2" />{labels.map((label, index) => { const [x, y] = axis(index).split(',').map(Number); return <text key={label} x={x} y={y + (y < center ? -7 : 14)} textAnchor="middle" className="fill-subtle text-[8px]">{label}</text> })}</svg><div className="flex items-center gap-4 text-[11px]"><span className="flex items-center gap-1.5 text-primary"><span className="size-2 rounded-full bg-primary" />Local</span><span className="flex items-center gap-1.5 text-positive"><span className="size-2 rounded-full bg-positive" />Visitante</span></div></div>
}

function TacticalRadar({ match, detail, h2h }: { match: Match; detail: MatchDetailData; h2h: MatchH2HData | null }) {
  const formValue = (form: Array<{ result: 'W' | 'D' | 'L' }>) => form.length ? form.reduce((sum, item) => sum + (item.result === 'W' ? 100 : item.result === 'D' ? 50 : 0), 0) / form.length : 50
  const refereeCards = match.refereeProfile?.yellow_cards_avg ?? 3.5
  const cornersHome = match.advancedStats?.home_corners ?? detail.cornersProb / 10
  const cornersAway = match.advancedStats?.away_corners ?? detail.cornersProb / 10
  const home = [Math.min(100, match.lambdaHome / 2.5 * 100), Math.max(0, 100 - match.lambdaAway / 2.5 * 100), Math.min(100, refereeCards * 15), Math.min(100, cornersHome * 10), formValue(h2h?.home_form ?? [])]
  const away = [Math.min(100, match.lambdaAway / 2.5 * 100), Math.max(0, 100 - match.lambdaHome / 2.5 * 100), Math.min(100, refereeCards * 15), Math.min(100, cornersAway * 10), formValue(h2h?.away_form ?? [])]
  return <div className="rounded-xl border border-[#252C35] bg-[#11151B] p-4"><div className="mb-2"><p className="text-[10px] tracking-[0.14em] text-subtle">Lectura táctica</p><h3 className="mt-1 text-base font-semibold text-foreground">Radar de forma y amenaza</h3></div><RadarChart home={home} away={away} /></div>
}

function H2HTab({
  match,
  enriched,
  model,
  detail,
  h2h,
}: {
  match: Match
  enriched: EnrichedMatch | null
  model: MatchModel
  detail: MatchDetailData
  h2h: MatchH2HData | null
}) {
  const hasLambdas = match.lambdaHome > 0 || match.lambdaAway > 0
  const homeForm = h2h?.home_form ?? []
  const awayForm = h2h?.away_form ?? []
  const h2hMatches = h2h?.h2h ?? []
  const goalEvents = h2hMatches.flatMap((item) => item.events.filter((event) => event.event_type === 'goal'))
  const secondHalfGoals = goalEvents.filter((event) => event.minute > 45).length
  const secondHalfShare = goalEvents.length ? Math.round((secondHalfGoals / goalEvents.length) * 100) : null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-center">
        <div className="flex items-center gap-1.5 text-[11px] text-subtle bg-surface/60 border border-border rounded-full px-3 py-1">
          <Sparkles size={10} className="text-primary" />
          Análisis Táctico · Groq · Llama 3.3
        </div>
      </div>

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 pt-4 pb-3">
          {sectionLabel({ children: 'Análisis Táctico & H2H' })}
        </div>

        <div className="px-4 pb-4 flex flex-col gap-4">
          {/* Recent form */}
          <div className="bg-surface/40 border border-border rounded-xl p-4">
              <p className="text-[10px] font-bold text-subtle tracking-[0.14em] mb-3">Forma Reciente · Últimos 5</p>
            <div className="flex items-center gap-3">
              <div className="flex flex-col gap-1.5 flex-1">
                <p className="text-[10px] font-bold text-subtle uppercase tracking-wider">{match.home}</p>
                <FormBubbles form={homeForm.map((item) => toFormResult(item.result))} />
              </div>
              <span className="text-[10px] font-bold text-muted-foreground uppercase">vs</span>
              <div className="flex flex-col gap-1.5 flex-1 items-end">
                <p className="text-[10px] font-bold text-subtle uppercase tracking-wider text-right">{match.away}</p>
                <FormBubbles form={awayForm.map((item) => toFormResult(item.result))} />
              </div>
            </div>
          </div>

          {/* Quantitative model */}
          {hasLambdas && (
            <div className="bg-surface/40 border border-border rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[10px] font-bold text-subtle uppercase tracking-widest">Modelo Cuantitativo</p>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-primary inline-block" /><span className="text-subtle">{match.home.split(' ')[0]}</span></span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-warning inline-block" /><span className="text-subtle">{match.away.split(' ')[0]}</span></span>
                </div>
              </div>
              <div className="flex flex-col gap-3">
                {/* xG row */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-black tabular-nums text-primary">{detail.homeExpectedGoals.toFixed(2)}</span>
                    <span className="text-[10px] text-subtle">Goles Esperados</span>
                    <span className="text-sm font-black tabular-nums text-warning">{detail.awayExpectedGoals.toFixed(2)}</span>
                  </div>
                  <div className="flex h-2 gap-px">
                    <div className="flex-1 bg-surface rounded-l-full overflow-hidden">
                      <div className="h-full bg-primary rounded-l-full ml-auto" style={{ width: `${Math.min((detail.homeExpectedGoals / 3) * 100, 100)}%` }} />
                    </div>
                    <div className="flex-1 bg-surface rounded-r-full overflow-hidden">
                      <div className="h-full bg-warning rounded-r-full" style={{ width: `${Math.min((detail.awayExpectedGoals / 3) * 100, 100)}%` }} />
                    </div>
                  </div>
                </div>
                {/* Total goals row */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-black tabular-nums text-primary">{detail.totalExpectedGoals.toFixed(2)} tot.</span>
                    <span className="text-[10px] text-subtle">Total Goles</span>
                    <span className="text-sm font-black tabular-nums text-warning">{detail.totalExpectedGoals.toFixed(2)} tot.</span>
                  </div>
                  <div className="flex h-2 gap-px">
                    <div className="flex-1 bg-surface rounded-l-full overflow-hidden">
                      <div className="h-full bg-primary/70 rounded-l-full ml-auto" style={{ width: `${Math.min((detail.totalExpectedGoals / 5) * 100, 100)}%` }} />
                    </div>
                    <div className="flex-1 bg-surface rounded-r-full overflow-hidden">
                      <div className="h-full bg-warning/70 rounded-r-full" style={{ width: `${Math.min((detail.totalExpectedGoals / 5) * 100, 100)}%` }} />
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                {detail.totalExpectedGoals < 2.2 && (
                  <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-subtle bg-surface border border-border rounded-full px-2.5 py-1">
                    <Lock size={10} />
                    Duelo cerrado
                  </span>
                )}
                {detail.homeExpectedGoals > detail.awayExpectedGoals + 0.5 && (
                  <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-subtle bg-surface border border-border rounded-full px-2.5 py-1">
                    <Home size={10} />
                    Local dominante
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Signal & narrative */}
          <div className="bg-surface/40 border border-border rounded-xl p-4">
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
            <p className="text-sm text-foreground leading-relaxed">
              <span className="font-bold text-foreground">Resumen:</span> {detail.aiSummaryPill || `${match.home} vs ${match.away}`} — {match.league}
            </p>
          </div>
        </div>
      </div>

      <TacticalRadar match={match} detail={detail} h2h={h2h} />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-[#252C35] bg-[#11151B] p-4">
          <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold text-foreground">Historial H2H</h3><span className="font-mono text-xs text-subtle">{h2hMatches.length} partidos</span></div>
          {h2hMatches.length ? <div className="flex flex-col divide-y divide-[#252C35]">{h2hMatches.map((item) => <div key={item.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"><div className="min-w-0"><p className="truncate text-xs font-medium text-foreground">{item.home_team} vs {item.away_team}</p><p className="mt-1 text-[10px] text-subtle">{new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'America/Bogota' }).format(new Date(item.match_date))}</p></div><span className="shrink-0 font-mono text-sm font-bold text-foreground">{item.home_score ?? '—'} - {item.away_score ?? '—'}</span></div>)}</div> : <p className="py-5 text-sm text-subtle">No hay enfrentamientos directos registrados.</p>}
        </div>
        <div className="rounded-xl border border-[#252C35] bg-[#11151B] p-4"><h3 className="text-sm font-semibold text-foreground">Contexto de minutos</h3>{secondHalfShare !== null ? <><p className="mt-3 font-mono text-3xl font-bold text-primary">{secondHalfShare}%</p><p className="mt-1 text-xs leading-5 text-subtle">de los goles registrados en H2H llegaron después del descanso.</p><div className="mt-4 h-2 overflow-hidden rounded-full bg-[#252C35]"><div className="h-full bg-primary" style={{ width: `${secondHalfShare}%` }} /></div></> : <p className="mt-5 text-sm leading-6 text-subtle">Los minutos exactos aparecerán cuando existan eventos históricos persistidos.</p>}</div>
      </div>

      {/* Narrative */}
      {detail.narrative && (
        <div className="bg-card/40 border border-border rounded-xl p-4">
          {sectionLabel({ children: 'Narrativa del Modelo', className: 'mb-3' })}
          <NarrativeBody text={detail.narrative} />
        </div>
      )}

      {!detail.narrative && enriched?.tacticalNarrative === '' && (
        <p className="rounded-xl border border-border bg-card/30 px-4 py-3 text-[11px] text-subtle text-center">
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
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 pt-4 pb-3">
          {sectionLabel({ children: 'Perfil del Árbitro' })}
          <span className="text-[10px] text-subtle bg-surface border border-border rounded-md px-2 py-0.5">
            {hasReferee ? match.referee.name : 'Por confirmar'}
          </span>
        </div>
        <div className="px-4 pb-4">
          {hasReferee ? (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-warning">{match.referee.yellows}</p>
                <p className="text-[10px] text-subtle mt-0.5">Amarillas prom.</p>
              </div>
              <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-negative">{match.referee.reds}</p>
                <p className="text-[10px] text-subtle mt-0.5">Rojas prom.</p>
              </div>
              <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
                <p className="text-xl font-black tabular-nums text-foreground">{match.referee.strictness}</p>
                <p className="text-[10px] text-subtle mt-0.5">Rigor (0–100)</p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center py-8 text-center border border-dashed border-border rounded-xl">
              <div className="w-14 h-14 rounded-full bg-surface/80 border border-border flex items-center justify-center mb-4">
                <User size={22} className="text-muted-foreground" />
              </div>
              <p className="text-sm font-bold text-foreground mb-1">Árbitro pendiente de confirmación</p>
              <p className="text-xs text-muted-foreground mb-4 leading-relaxed">
                Normalmente se confirma <span className="font-semibold text-subtle">4–6 horas</span>
                <br />antes del partido
              </p>
              <button
                onClick={() => setNotified(s => !s)}
                className={cn(
                  'flex items-center gap-2 text-xs font-bold px-4 py-2 rounded-lg border transition-all',
                  notified
                    ? 'bg-primary/15 border-primary/30 text-primary'
                    : 'bg-surface border-border text-foreground hover:border-primary/40 hover:text-foreground'
                )}
              >
                <Bell size={12} className={notified ? 'text-primary' : ''} />
                {notified ? 'Notificación activada' : 'Notificarme cuando se confirme'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* League context */}
      <div className="bg-card border border-border rounded-xl p-4">
        {sectionLabel({ children: 'Contexto de la Liga', className: 'mb-3' })}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-warning/20 border border-warning/30 flex items-center justify-center mx-auto mb-2">
              <div className="w-3 h-4 bg-warning rounded-sm" />
            </div>
            <p className="text-xl font-black tabular-nums text-foreground">{detail.avgCards}</p>
            <p className="text-[10px] text-subtle mt-0.5">Tarjetas prom. Liga</p>
            <p className="text-[10px] text-muted-foreground">por partido</p>
          </div>
          <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-negative/20 border border-negative/30 flex items-center justify-center mx-auto mb-2">
              <div className="w-3 h-4 bg-negative rounded-sm" />
            </div>
            <p className="text-xl font-black tabular-nums text-foreground">{detail.avgReds}</p>
            <p className="text-[10px] text-subtle mt-0.5">Rojas prom. Liga</p>
            <p className="text-[10px] text-muted-foreground">por partido</p>
          </div>
          <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
            <div className="w-7 h-7 rounded-md bg-muted border border-border flex items-center justify-center mx-auto mb-2">
              <ShieldAlert size={14} className="text-subtle" />
            </div>
            <p className="text-xl font-black tabular-nums text-foreground">{detail.avgFouls}</p>
            <p className="text-[10px] text-subtle mt-0.5">Faltas prom. liga</p>
            <p className="text-[10px] text-muted-foreground">por partido</p>
          </div>
        </div>
        <div className="flex items-start gap-2.5 mt-3 bg-warning/5 border border-warning/15 rounded-lg px-3 py-2.5">
          <Lightbulb size={14} className="text-warning mt-0.5 shrink-0" />
          <p className="text-xs text-subtle leading-relaxed">
            <span className="font-bold text-foreground">Consejo:</span> En este mercado, el árbitro puede mover las cuotas de tarjetas hasta un{' '}
            <span className="font-bold text-warning">15–25%</span>. Espera la confirmación antes de apostar en mercados de disciplina.
          </p>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* MatchDetailContent                                                  */
/* ------------------------------------------------------------------ */

function MatchDetailContent({ match, enriched, h2h }: { match: Match; enriched?: EnrichedMatch | null; h2h: MatchH2HData | null }) {
  const [activeTab, setActiveTab] = React.useState<MatchTab>('preview')
  const model = React.useMemo(() => buildModel(match.lambdaHome, match.lambdaAway), [match])
  const rows  = React.useMemo(() => marketRows(match, model), [match, model])
  const best  = React.useMemo(() => {
    const sorted = [...rows].sort((a, b) => b.edge - a.edge)
    return sorted[0] && sorted[0].edge >= 0.03 ? sorted[0] : null
  }, [rows])
  const detail = React.useMemo(() => buildDetail(match, enriched ?? null, model), [match, enriched, model])
  const leagueMeta = resolveLeague(match.leagueExternalId, match.league)
  const mainEdge = Math.max(...rows.filter((row) => row.key === 'home' || row.key === 'draw' || row.key === 'away').map((row) => row.edge), 0)

  return (
    <div className="flex flex-col gap-4">
      <MatchHero match={match} leagueMeta={leagueMeta} model={model} />

      <SignalRail match={match} detail={detail} enriched={enriched ?? null} marketEdge={mainEdge} />

      {detail.confidenceScore > 0 && (
        <ConfidenceBar detail={detail} model={model} />
      )}

      <MatchTabBar active={activeTab} onChange={setActiveTab} />

      {activeTab === 'preview' && (
        <PreviaTab match={match} enriched={enriched ?? null} model={model} rows={rows} best={best} detail={detail} />
      )}
      {activeTab === 'markets' && <QuantMarkets enriched={enriched ?? null} />}
      {activeTab === 'builder' && (
        <div className="rounded-xl border border-border bg-card p-4">
          <BetBuilder detail={detail} />
        </div>
      )}
      {activeTab === 'h2h' && (
        <H2HTab match={match} enriched={enriched ?? null} model={model} detail={detail} h2h={h2h} />
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
  const [h2h, setH2H] = React.useState<MatchH2HData | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError]     = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [predictionResult, h2hResult] = await Promise.allSettled([
          fetchMatchPrediction(params.id),
          fetchMatchH2H(params.id),
        ])
        const prediction = predictionResult.status === 'fulfilled' ? predictionResult.value : null
        if (!cancelled) {
          if (h2hResult.status === 'fulfilled' && h2hResult.value.ok) setH2H(h2hResult.value.data)
          if (prediction?.ok && prediction.data) {
            setMatch(prediction.data)
            setEnriched(prediction.data)
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
    <div className="min-h-svh bg-background pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-3 px-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-subtle hover:text-foreground transition-colors"
          >
            <ArrowLeft size={14} />
            Volver a Partidos
          </Link>
          {match && (
            <h1 className="ml-auto truncate text-sm font-bold text-foreground">
              {match.home} vs {match.away}
            </h1>
          )}
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-5">
          {loading && <PageSkeleton />}
          {error && !loading && (
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-10 text-center">
              <p className="text-sm font-medium text-foreground">Partido no encontrado</p>
              <p className="mt-1 text-xs text-subtle">
                Es posible que el partido ya no esté disponible para hoy.
              </p>
              <Link
                href="/"
                className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
              >
                <ArrowLeft size={14} />
                Volver al inicio
              </Link>
            </div>
          )}
          {match && !loading && <MatchDetailContent match={match} enriched={enriched} h2h={h2h} />}
        </div>
      </div>
    </div>
  )
}
