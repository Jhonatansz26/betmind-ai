'use client'

import * as React from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import {
  ArrowLeft,
  Target,
  Activity,
  Flame,
  Sparkles,
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
} from 'lucide-react'

import {
  buildModel,
  marketRows,
  type Match,
  type MatchModel,
  type MarketRow,
} from '@/lib/betmind'
import { fetchMatchH2H, fetchMatchPrediction, type EnrichedMatch, type MatchH2HData } from '@/lib/api'
import { resolveLeague } from '@/lib/league-metadata'
import { formatMarketName } from '@/lib/formatMarketName'
import { formatEV, formatOdds, formatPercent, formatxG } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { TeamLogo } from '@/components/ui/team-logo'
import { LeagueLogo } from '@/components/betmind/league-logo'
import { MatchTabBar, type MatchTab } from '@/components/betmind/match-tab-bar'
import { MarketTable } from '@/components/betmind/market-table'
import { BetBuilderCards } from '@/components/betmind/bet-builder-cards'
import { TacticalPanel } from '@/components/betmind/tactical-panel'
import { StatDisclaimer } from '@/components/betmind/stat-disclaimer'
import { useProStatus } from '@/components/betmind/use-pro-status'

/* ------------------------------------------------------------------ */
/* Local types                                                         */
/* ------------------------------------------------------------------ */

type FormResult = 'V' | 'E' | 'D'

interface MatchDetailData {
  confidenceScore: number
  riskLevel: string
  probableScore: string
  underOverLabel: string
  underOverProb: number
  aiSummaryPill: string
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

function buildDetail(match: Match, enriched: EnrichedMatch | null, model: MatchModel): MatchDetailData {
  const over25 = model.over25
  const underOverLabel = over25 > 0.5 ? 'Más de 2.5' : 'Menos de 2.5'
  const underOverProb = over25 > 0.5 ? over25 * 100 : (1 - over25) * 100

  const signalMap: Record<string, number> = { STRONG: 3, MODERATE: 2, WEAK: 1 }
  const signalStrength = signalMap[match.signal] ?? 1

  const evAnalysis = enriched?.evAnalysis ?? []

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
        <LeagueLogo logoUrl={leagueMeta.logoUrl} flag={leagueMeta.flag} label={leagueMeta.shortName} size="sm" />
        <span className="text-xs font-semibold text-subtle">{leagueMeta.name}</span>
        <span className="text-muted-foreground text-xs">·</span>
         <span className="font-mono text-xs text-subtle tabular-nums">{match.time}</span>
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
             <span className="font-mono text-2xl font-black tabular-nums text-foreground tracking-wide">
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
               <p className="font-mono text-lg font-black tabular-nums text-primary">{formatPercent(model.home)}</p>
            </div>
            <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
              <p className="text-[10px] font-semibold text-subtle uppercase tracking-wider mb-1.5">Empate</p>
               <p className="font-mono text-lg font-black tabular-nums text-foreground">{formatPercent(model.draw)}</p>
            </div>
            <div className="bg-surface/50 border border-border/50 rounded-xl p-3 text-center">
              <p className="text-[10px] font-semibold text-subtle uppercase tracking-wider mb-1.5">Visitante</p>
               <p className="font-mono text-lg font-black tabular-nums text-warning">{formatPercent(model.away)}</p>
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
            className="h-full rounded-full bg-gradient-to-r from-primary to-primary/70 transition-[width]"
            style={{ width: `${detail.confidenceScore}%` }}
          />
        </div>
        <span className="font-mono text-[11px] font-bold text-foreground tabular-nums shrink-0">{detail.confidenceScore}/100</span>
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
       <div className="rounded-2xl border border-warning/25 bg-[var(--surface)] p-5">
       <div className="rounded-xl border border-warning/20 bg-warning/[0.06] p-4"><p className="text-sm font-semibold text-warning">Veredicto BetMind: Protege tu Capital</p><p className="mt-2 text-sm leading-6 text-foreground/80">Las cuotas 1X2 están perfectamente ajustadas por el mercado (0% EV). Explora los mercados secundarios a continuación.</p></div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
        <div><p className="terminal-label">Radar táctico · xG</p><div className="mt-3 flex items-end justify-between"><span className="font-mono text-lg font-bold tabular-nums text-primary">{formatxG(detail.homeExpectedGoals)}</span><span className="text-xs text-subtle">Goles esperados</span><span className="font-mono text-lg font-bold tabular-nums text-warning">{formatxG(detail.awayExpectedGoals)}</span></div><div className="mt-2 flex h-3 overflow-hidden rounded-full bg-[var(--surface-raised)]"><div className="bg-primary" style={{ width: `${homeWidth}%` }} /><div className="bg-warning" style={{ width: `${100 - homeWidth}%` }} /></div><div className="mt-2 flex justify-between text-xs text-subtle"><span>{match.home}</span><span>{match.away}</span></div></div>
        <div className="grid grid-cols-2 gap-2"><div className="rounded-lg border border-[var(--surface-raised)] bg-[var(--surface-inset)]/60 p-3"><p className="text-[10px] text-subtle">Córneres</p><p className="mt-1 text-sm font-semibold text-foreground">{detail.cornersLine} · {detail.cornersProb}%</p></div><div className="rounded-lg border border-[var(--surface-raised)] bg-[var(--surface-inset)]/60 p-3"><p className="text-[10px] text-subtle">Fricción</p><p className="mt-1 text-sm font-semibold text-foreground">{detail.cardsFriction}</p></div><div className="col-span-2 rounded-lg border border-[var(--surface-raised)] bg-[var(--surface-inset)]/60 p-3"><p className="text-[10px] text-subtle">Perfil del árbitro</p><p className="mt-1 text-sm font-semibold text-foreground">{match.refereeProfile?.name ?? 'Pendiente de confirmación'}</p></div></div>
      </div>
    </div>
  )
}

type QuantMarket = EnrichedMatch['evAnalysis'][number]

const MARKET_GROUPS = [
  { id: 'goals', label: 'Goles & Resultado', match: (market: string) => !market.startsWith('CORNERS_') && !market.startsWith('CARDS_') && !market.startsWith('SHOTS_OT_') },
  { id: 'corners', label: 'Córneres Totales', match: (market: string) => market.startsWith('CORNERS_') },
  { id: 'cards', label: 'Tarjetas & Disciplina', match: (market: string) => market.startsWith('CARDS_') },
  { id: 'shots', label: 'Remates a Puerta', match: (market: string) => market.startsWith('SHOTS_OT_') },
] as const

function MarketAccordion({ label, markets, defaultOpen = false }: { label: string; markets: QuantMarket[]; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(defaultOpen)
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex min-h-11 w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        <span className="text-sm font-semibold text-foreground">{label}</span><span className="flex items-center gap-2 font-mono text-xs text-subtle">{markets.length}<ChevronDown size={15} className={cn('transition-transform', open && 'rotate-180')} aria-hidden="true" /></span>
      </button>
      {open && (
        <div className="border-t border-[var(--surface-raised)] p-2">
          <div className="hidden grid-cols-[minmax(0,1fr)_minmax(120px,0.8fr)_90px_110px] gap-3 px-3 py-2 text-[10px] tracking-[0.12em] text-subtle sm:grid">
            <span>Mercado</span><span>Probabilidad IA</span><span>Edge</span><span>Estado</span>
          </div>
          {markets.length === 0 ? <p className="px-3 py-4 text-sm text-subtle">Sin mercados disponibles.</p> : markets.map((market) => {
            const reliable = market.probability >= 0.70 && market.ev > 0
            const risky = market.probability < 0.35
            const probability = market.probability * 100
            return (
              <div key={market.market} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 rounded-lg px-3 py-3 even:bg-[var(--surface-inset)]/50 sm:grid-cols-[minmax(0,1fr)_minmax(120px,0.8fr)_90px_110px] sm:gap-3">
                <span className="min-w-0 truncate font-sans text-sm text-foreground">{formatMarketName(market.market)}</span>
                <div className="flex min-w-[112px] flex-col gap-1">
                  <span className="font-mono text-right text-sm font-semibold tabular-nums text-foreground sm:text-left">{formatPercent(market.probability)}</span>
                  <div className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-raised)]"><div className={cn('h-full rounded-full', market.ev > 0 ? 'bg-[var(--positive)]' : 'bg-[var(--home-team)]')} style={{ width: `${Math.max(4, Math.min(100, probability))}%` }} /></div>
                </div>
                <span className={cn('font-mono text-right text-sm font-semibold tabular-nums', market.ev > 0 ? 'text-positive' : 'text-subtle')}>{formatEV(market.ev)} EV</span>
                <span className={cn('col-span-2 justify-self-end text-[10px] font-semibold sm:col-span-1 sm:justify-self-start', reliable && 'rounded-md border border-[var(--positive)]/25 bg-[var(--positive)]/10 px-2 py-1 text-[var(--positive)]', risky && 'rounded-md border border-negative/25 bg-negative/10 px-2 py-1 text-negative', !reliable && !risky && 'text-subtle')}>
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

function SignalMarketCard({ market }: { market: QuantMarket }) {
  const modelPct = Math.max(0, Math.min(100, market.probability * 100))
  const impliedPct = market.odds > 1 ? Math.min(100, (1 / market.odds) * 100) : null
  const positiveValue = market.ev > 0
  const verdict = market.verdict === 'NO_ODDS_AVAILABLE' ? 'SIN CUOTAS' : positiveValue ? 'POSITIVE_EV' : market.probability >= 0.65 ? 'NO_VALUE' : 'AVOID'
  return <article className={cn('rounded-xl border bg-card p-4 transition-[border-color,background-color,transform] duration-200 ease-out hover:-translate-y-0.5 hover:bg-surface/50', positiveValue ? 'border-positive/30' : 'border-border')}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-semibold text-foreground">{formatMarketName(market.market)}</p><p className="mt-1 font-mono text-[10px] text-muted-foreground">56M · {market.odds > 1 ? `Cuota ${formatOdds(market.odds)}` : 'Cuota no publicada'}</p></div><span className={cn('rounded border px-2 py-1 font-mono text-[10px] font-bold', positiveValue ? 'border-positive/30 bg-positive/10 text-positive' : verdict === 'AVOID' ? 'border-negative/25 bg-negative/10 text-negative' : 'border-border/60 bg-surface text-muted-foreground')}>{verdict}</span></div><div className="mt-4 grid gap-2 font-mono text-[9px] text-muted-foreground"><div className="flex items-center gap-2"><span className="w-12 shrink-0">MODELO</span><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-inset"><div className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out" style={{ width: `${modelPct}%` }} /></div><span className="w-10 text-right tabular-nums text-foreground">{modelPct.toFixed(1)}%</span></div><div className="flex items-center gap-2"><span className="w-12 shrink-0">CASA</span><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-inset"><div className="h-full rounded-full bg-muted-foreground/60" style={{ width: `${impliedPct ?? 0}%` }} /></div><span className="w-10 text-right tabular-nums text-foreground">{impliedPct != null ? `${impliedPct.toFixed(1)}%` : 'N/D'}</span></div></div><div className="mt-4 border-t border-border/60 pt-3"><div><p className="text-[10px] text-muted-foreground">Edge / EV</p><p className={cn('mt-1 font-mono text-lg font-bold tabular-nums', positiveValue ? 'text-positive' : 'text-foreground')}>{market.edge >= 0 ? '+' : ''}{(market.edge * 100).toFixed(1)}% <span className="text-xs">· {market.ev >= 0 ? '+' : ''}{(market.ev * 100).toFixed(1)}% EV</span></p></div></div></article>
}

function QuantMarkets({ enriched }: { enriched: EnrichedMatch | null }) {
  const allMarkets = enriched?.evAnalysis ?? []
  const [showAll, setShowAll] = React.useState(false)
  // TODO(backend-pagos): reemplazar por chequeo real de suscripción.
  const isPro = useProStatus()
  const markets = isPro ? allMarkets : allMarkets.slice(0, 10)
  const signals = [...markets].filter((market) => market.ev > 0 || market.probability > 0.65).sort((a, b) => (b.ev - a.ev) || (b.probability - a.probability)).slice(0, 5)
  return <div className="flex flex-col gap-4"><div className="flex items-end justify-between"><div><p className="text-[10px] tracking-[0.14em] text-subtle">Señales filtradas · 80/20</p><h2 className="mt-1 text-lg font-semibold text-foreground">Señales de margen +EV</h2></div><span className="font-mono text-xs text-primary">{markets.length}/56 mercados</span></div>{signals.length > 0 ? <div className="grid gap-3 lg:grid-cols-2">{signals.map((market) => <SignalMarketCard key={market.market} market={market} />)}</div> : <div className="rounded-xl border border-dashed border-[var(--surface-raised)] bg-[var(--surface)] px-5 py-8 text-center text-sm text-subtle">No hay señales destacadas en este partido. El mercado está ajustado.</div>}<button type="button" onClick={() => setShowAll((value) => !value)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[var(--surface-raised)] bg-[var(--surface)] px-4 text-sm font-semibold text-subtle transition-colors hover:border-primary/50 hover:text-foreground">{showAll ? 'Ocultar catálogo completo' : 'Explorar los 56 mercados completos · Modo Analista'}</button>{showAll && <div className="flex flex-col gap-3 pt-2">{MARKET_GROUPS.map((group, index) => <MarketAccordion key={group.id} label={group.label} markets={markets.filter((market) => group.match(market.market))} defaultOpen={index === 0} />)}</div>}<p className="text-xs leading-5 text-subtle">Las señales priorizan valor o probabilidad relevante. Las cuotas no publicadas se muestran como N/D, nunca como una oportunidad inventada.</p></div>
}

function LockedMarkets({ markets }: { markets: QuantMarket[] }) {
  const lockedMarkets = markets.slice(10)
  if (!lockedMarkets.length) return null
  return (
    <div className="relative overflow-hidden rounded-xl border border-brand/30 bg-surface">
      <div aria-hidden="true" className="pointer-events-none max-h-[380px] overflow-hidden p-3 opacity-40 blur-[3px]">
        <div className="grid gap-3 lg:grid-cols-2">{lockedMarkets.map((market) => <SignalMarketCard key={market.market} market={market} />)}</div>
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/55 px-5 text-center backdrop-blur-[1px]">
        <p className="text-sm font-semibold text-foreground">Estás viendo 10 de 56 mercados</p>
        <p className="mt-2 max-w-md text-xs leading-5 text-muted-foreground">El resto del análisis cuantitativo completo — córneres, tarjetas, remates y más — está en PRO.</p>
        <Link href="/planes" className="mt-4 inline-flex min-h-10 items-center rounded-lg bg-brand px-4 text-xs font-bold text-primary-foreground hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand">Desbloquear todo →</Link>
      </div>
    </div>
  )
}

function ScouterStats({ match }: { match: Match }) {
  const stats = match.advancedStats
  const hasStats = Boolean(stats && Object.values(stats).some((value) => typeof value === 'number'))
  if (!hasStats) return <div className="rounded-xl border border-dashed border-border bg-card px-5 py-8 text-center"><BarChart3 size={20} className="mx-auto text-primary" aria-hidden="true" /><p className="mt-3 text-sm font-semibold text-foreground">Datos en vivo al finalizar el partido</p><p className="mt-1 text-xs leading-5 text-subtle">Corners, remates, faltas y eventos aparecerán cuando termine el encuentro.</p></div>
  const items = [['Corners', stats?.home_corners, stats?.away_corners], ['Remates', stats?.home_shots, stats?.away_shots], ['A puerta', stats?.home_shots_on_target, stats?.away_shots_on_target], ['Faltas', stats?.home_fouls, stats?.away_fouls]] as const
  return <div className="rounded-xl border border-border bg-card p-4"><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold text-foreground">Datos Scouter</h2><span className="text-xs text-positive">Datos verificados</span></div><div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{items.map(([label, home, away]) => <div key={label} className="rounded-lg border border-border bg-surface-raised/50 p-3"><p className="text-[10px] text-subtle">{label}</p><p className="mt-1 font-mono text-sm font-semibold text-foreground">{home ?? '—'} <span className="text-subtle">·</span> {away ?? '—'}</p></div>)}</div>{match.refereeProfile && <p className="mt-3 text-xs text-subtle">Árbitro: <span className="text-foreground">{match.refereeProfile.name}</span> · {match.refereeProfile.yellow_cards_avg.toFixed(1)} amarillas por partido</p>}</div>
}

function PrimaryRecommendation({ best }: { best: MarketRow | null }) {
  if (!best) return <div className="rounded-xl border border-dashed border-[var(--surface-raised)] bg-[var(--surface)] p-5"><p className="text-[10px] tracking-[0.14em] text-subtle">Pronóstico principal</p><p className="mt-3 text-sm text-subtle">No hay una ventaja suficiente para recomendar una selección.</p></div>
  return <div className="rounded-xl border border-positive/25 bg-card p-5"><div className="flex items-start justify-between gap-4"><div><p className="terminal-label text-positive">Pronóstico principal · +EV máximo</p><h2 className="mt-2 text-xl font-semibold text-foreground">{best.label}</h2><p className="mt-1 text-sm text-subtle">Ventaja detectada sobre la probabilidad implícita del mercado.</p></div><span className="rounded-lg border border-positive/30 bg-positive/10 px-2.5 py-1 font-mono text-sm font-bold tabular-nums text-positive">{formatEV(best.edge)}</span></div><div className="mt-5 border-t border-border/60 pt-4"><p className="terminal-label">Cuota disponible</p><p className="mt-1 font-mono text-2xl font-bold tabular-nums text-foreground">{formatOdds(best.odds)}</p></div></div>
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
                 'shrink-0 w-14 text-center font-mono font-black tabular-nums rounded-lg py-1.5 text-sm border',
                i === 0
                  ? 'bg-positive/10 border-positive/25 text-positive'
                  : 'bg-surface/60 border-border/60 text-foreground'
              )}>
                {s.score}
              </div>
              <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-[width]', i === 0 ? 'bg-positive' : 'bg-primary/60')}
                  style={{ width: `${barWidth}%` }}
                />
              </div>
              <div className="shrink-0 flex items-center gap-2">
                   <span className={cn('font-mono text-xs font-bold tabular-nums w-10 text-right', i === 0 ? 'text-positive' : 'text-subtle')}>
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
               <span className="font-mono text-xs font-bold text-foreground tabular-nums w-10 shrink-0">{row.home.toFixed(1)}%</span>
              <div className="flex-1 flex gap-px">
                <div className="flex-1 h-1.5 bg-surface rounded-l-full overflow-hidden">
                  <div className="h-full bg-primary rounded-l-full ml-auto" style={{ width: `${Math.min(row.home, 100)}%` }} />
                </div>
                <div className="flex-1 h-1.5 bg-surface rounded-r-full overflow-hidden">
                  <div className="h-full bg-warning rounded-r-full" style={{ width: `${Math.min(row.away, 100)}%` }} />
                </div>
              </div>
               <span className="font-mono text-xs font-bold text-foreground tabular-nums w-10 shrink-0 text-right">{row.away.toFixed(1)}%</span>
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
          <p className="font-mono text-xl font-black text-foreground tabular-nums">+{detail.cornersLine}</p>
          <p className="text-xs text-subtle mt-0.5">Prob. Over: <span className="text-foreground font-semibold">{detail.cornersProb}%</span></p>
        </div>
        <div className="bg-surface/50 border border-border/50 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-sm bg-negative/20 border border-negative/30 flex items-center justify-center">
              <span className="text-[9px] font-black text-negative">T</span>
            </div>
            <span className="text-[10px] font-bold text-subtle uppercase tracking-wider">Tarjetas</span>
          </div>
          <p className="font-mono text-xl font-black text-foreground tabular-nums">{detail.cardsLine}+</p>
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
      <TacticalPanel
        match={match}
        analysis={{
          confidence_score: enriched?.confidenceScore ?? detail.confidenceScore,
          risk_level: enriched?.riskLevel ?? detail.riskLevel,
          llm_model_used: enriched?.llmModelUsed,
          match_preview_headline: enriched?.tacticalHeadline || detail.aiSummaryPill,
          data_completeness_score: enriched?.tacticalAnalysis?.data_completeness_score,
        }}
      />
       <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Left */}
         <div className="flex flex-col gap-5 min-w-0">
           {mainEdge >= 0.03 ? <PrimaryRecommendation best={best} /> : <CapitalProtectionPanel match={match} detail={detail} />}
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
  return <div className="flex flex-col items-center gap-3"><svg viewBox="0 0 200 200" className="h-64 w-64" role="img" aria-label="Comparativa táctica de cinco métricas"><polygon points={labels.map((_, index) => axis(index)).join(' ')} fill="none" stroke="var(--border)" strokeWidth="1" />{[25, 50, 75].map((scale) => <polygon key={scale} points={labels.map((_, index) => point(scale, index)).join(' ')} fill="none" stroke="var(--border)" strokeWidth="0.7" opacity="0.8" />)}{labels.map((label, index) => <line key={label} x1={center} y1={center} x2={axis(index).split(',')[0]} y2={axis(index).split(',')[1]} stroke="var(--border)" strokeWidth="0.7" />)}<polygon points={home.map((value, index) => point(value, index)).join(' ')} fill="var(--home-team)" opacity="0.20" stroke="var(--home-team)" strokeWidth="2" /><polygon points={away.map((value, index) => point(value, index)).join(' ')} fill="var(--away-team)" opacity="0.12" stroke="var(--away-team)" strokeWidth="2" />{labels.map((label, index) => { const [x, y] = axis(index).split(',').map(Number); return <text key={label} x={x} y={y + (y < center ? -7 : 14)} textAnchor="middle" className="fill-subtle text-[8px]">{label}</text> })}</svg><div className="flex items-center gap-4 text-[11px]"><span className="flex items-center gap-1.5 text-primary"><span className="size-2 rounded-full bg-primary" />Local</span><span className="flex items-center gap-1.5 text-positive"><span className="size-2 rounded-full bg-positive" />Visitante</span></div></div>
}

function TacticalRadar({ match, detail, h2h }: { match: Match; detail: MatchDetailData; h2h: MatchH2HData | null }) {
  const formValue = (form: Array<{ result: 'W' | 'D' | 'L' }>) => form.length ? form.reduce((sum, item) => sum + (item.result === 'W' ? 100 : item.result === 'D' ? 50 : 0), 0) / form.length : 50
  const refereeCards = match.refereeProfile?.yellow_cards_avg ?? 3.5
  const cornersHome = match.advancedStats?.home_corners ?? detail.cornersProb / 10
  const cornersAway = match.advancedStats?.away_corners ?? detail.cornersProb / 10
  const home = [Math.min(100, match.lambdaHome / 2.5 * 100), Math.max(0, 100 - match.lambdaAway / 2.5 * 100), Math.min(100, refereeCards * 15), Math.min(100, cornersHome * 10), formValue(h2h?.home_form ?? [])]
  const away = [Math.min(100, match.lambdaAway / 2.5 * 100), Math.max(0, 100 - match.lambdaHome / 2.5 * 100), Math.min(100, refereeCards * 15), Math.min(100, cornersAway * 10), formValue(h2h?.away_form ?? [])]
  return <div className="rounded-xl border border-[var(--surface-raised)] bg-[var(--surface)] p-4"><div className="mb-2"><p className="text-[10px] tracking-[0.14em] text-subtle">Lectura táctica</p><h3 className="mt-1 text-base font-semibold text-foreground">Radar de forma y amenaza</h3></div><RadarChart home={home} away={away} /></div>
}

function H2HReferencePanel({ match, detail, h2h }: { match: Match; detail: MatchDetailData; h2h: MatchH2HData | null }) {
  const metrics = [
    { label: 'xG del modelo', home: detail.homeExpectedGoals, away: detail.awayExpectedGoals },
    { label: 'Córneres', home: match.advancedStats?.home_corners ?? null, away: match.advancedStats?.away_corners ?? null },
  ]
  return <div className="rounded-xl border border-border bg-card p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold tracking-[0.14em] text-subtle">MATRIZ DE DOMINIO</p><h3 className="mt-1 text-base font-semibold text-foreground">Referencia bilateral</h3></div>{h2h?.total ? <span className="font-mono text-[10px] text-primary">{h2h.total} H2H verificados</span> : <span className="rounded border border-warning/25 bg-warning/10 px-2 py-1 text-[10px] font-mono text-warning">H2H DIRECTO NO DISPONIBLE</span>}</div>{!h2h?.total && <p className="mt-3 rounded-lg border border-border/60 bg-surface/50 px-3 py-2 text-xs leading-5 text-muted-foreground">La muestra directa aún no está persistida. Se muestra la referencia del modelo actual y la forma reciente como degradación trazable, sin inventar promedios históricos.</p>}<div className="mt-4 flex flex-col gap-3">{metrics.map((metric) => { const total = (metric.home ?? 0) + (metric.away ?? 0); const homePct = total > 0 ? ((metric.home ?? 0) / total) * 100 : 50; return <div key={metric.label} className="grid gap-1.5"><div className="flex items-center justify-between gap-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground"><span className="text-primary">{metric.home != null ? metric.home.toFixed(2) : 'N/D'}</span><span>{metric.label}</span><span className="text-warning">{metric.away != null ? metric.away.toFixed(2) : 'N/D'}</span></div><div className="flex h-2 gap-1 overflow-hidden"><div className="flex-1 rounded-l-full bg-surface-inset"><div className="ml-auto h-full rounded-l-full bg-primary transition-[width] duration-300 ease-out" style={{ width: `${metric.home != null ? homePct : 0}%` }} /></div><div className="flex-1 rounded-r-full bg-surface-inset"><div className="h-full rounded-r-full bg-warning transition-[width] duration-300 ease-out" style={{ width: `${metric.away != null ? 100 - homePct : 0}%` }} /></div></div></div> })}</div><div className="mt-4 grid grid-cols-2 gap-2 text-[10px] text-muted-foreground"><div className="rounded-lg border border-primary/15 bg-primary/[0.05] p-2"><span className="block uppercase tracking-wider text-primary">Local</span><span className="mt-1 block truncate">{match.home}</span></div><div className="rounded-lg border border-warning/15 bg-warning/[0.05] p-2 text-right"><span className="block uppercase tracking-wider text-warning">Visitante</span><span className="mt-1 block truncate">{match.away}</span></div></div></div>
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
                    <span className="font-mono text-sm font-black tabular-nums text-primary">{detail.homeExpectedGoals.toFixed(2)}</span>
                    <span className="text-[10px] text-subtle">Goles Esperados</span>
                    <span className="font-mono text-sm font-black tabular-nums text-warning">{detail.awayExpectedGoals.toFixed(2)}</span>
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
                    <span className="font-mono text-sm font-black tabular-nums text-primary">{detail.totalExpectedGoals.toFixed(2)} tot.</span>
                    <span className="text-[10px] text-subtle">Total Goles</span>
                    <span className="font-mono text-sm font-black tabular-nums text-warning">{detail.totalExpectedGoals.toFixed(2)} tot.</span>
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

      <H2HReferencePanel match={match} detail={detail} h2h={h2h} />

      <TacticalRadar match={match} detail={detail} h2h={h2h} />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-[var(--surface-raised)] bg-[var(--surface)] p-4">
          <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold text-foreground">Historial H2H</h3><span className="font-mono text-xs text-subtle">{h2hMatches.length} partidos</span></div>
          {h2hMatches.length ? <div className="flex flex-col divide-y divide-[var(--surface-raised)]">{h2hMatches.map((item) => <div key={item.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"><div className="min-w-0"><p className="truncate text-xs font-medium text-foreground">{item.home_team} vs {item.away_team}</p><p className="mt-1 text-[10px] text-subtle">{new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'America/Bogota' }).format(new Date(item.match_date))}</p></div><span className="shrink-0 font-mono text-sm font-bold text-foreground">{item.home_score ?? '—'} - {item.away_score ?? '—'}</span></div>)}</div> : <p className="py-5 text-sm text-subtle">No hay enfrentamientos directos registrados.</p>}
        </div>
        <div className="rounded-xl border border-[var(--surface-raised)] bg-[var(--surface)] p-4"><h3 className="text-sm font-semibold text-foreground">Contexto de minutos</h3>{secondHalfShare !== null ? <><p className="mt-3 font-mono text-3xl font-bold text-primary">{secondHalfShare}%</p><p className="mt-1 text-xs leading-5 text-subtle">de los goles registrados en H2H llegaron después del descanso.</p><div className="mt-4 h-2 overflow-hidden rounded-full bg-[var(--surface-raised)]"><div className="h-full bg-primary" style={{ width: `${secondHalfShare}%` }} /></div></> : <p className="mt-5 text-sm leading-6 text-subtle">Los minutos exactos aparecerán cuando existan eventos históricos persistidos.</p>}</div>
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
  // TODO(backend-pagos): reemplazar por chequeo real de suscripción.
  const isPro = useProStatus()

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
      {activeTab === 'markets' && <div className="flex flex-col gap-3"><QuantMarkets enriched={enriched ?? null} />{!isPro && <LockedMarkets markets={enriched?.evAnalysis ?? []} />}<StatDisclaimer /></div>}
      {activeTab === 'builder' && (
        isPro ? (
          detail.betBuilder && detail.betBuilder.length > 0 && <div className="rounded-xl border border-border bg-card p-4"><BetBuilderCards profiles={detail.betBuilder} /></div>
        ) : (
          <div className="relative overflow-hidden rounded-xl border border-brand/30 bg-surface">
            <div aria-hidden="true" className="pointer-events-none opacity-40 blur-[3px] p-3"><BetBuilderCards profiles={(detail.betBuilder ?? []).slice(0, 1)} /></div>
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/55 px-5 text-center backdrop-blur-[1px]"><p className="text-sm font-semibold text-foreground">Las estrategias correlacionadas son PRO. Desbloqueálas.</p><Link href="/planes" className="mt-4 inline-flex min-h-10 items-center rounded-lg bg-brand px-4 text-xs font-bold text-primary-foreground hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand">Ver planes →</Link></div>
          </div>
        )
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
