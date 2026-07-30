// BetMind AI — Poisson model helpers and mock intelligence data.

export type Mode = 'EDGE' | 'VALUE' | 'BOLD'
export type MatchStatus = 'SCHEDULED' | 'IN_PLAY' | 'PAUSED' | 'FINISHED' | 'UPCOMING' | 'LIVE' | 'FT'
export type Impact = 'HIGH' | 'MEDIUM' | 'LOW'

export interface League {
  id: string
  name: string
  flag: string
  matches: number
  region: 'EUROPE' | 'AMERICAS'
  logoUrl: string | null
}

export interface TacticalFactor {
  category: 'FORM' | 'H2H' | 'STATISTICS' | 'CONTEXT' | 'REFEREE'
  factor: string
  impact: Impact
}

export interface Referee {
  name: string
  yellows: number
  reds: number
  fouls: number
  strictness: number // 0-100
  highStakes: number
  trend: string
}

export interface MarketOdds {
  key: 'home' | 'draw' | 'away' | 'over25' | 'btts'
  label: string
  odds: number
}

export interface Match {
  id: string
  leagueId: string
  leagueExternalId: number | null
  league: string
  leagueCountry: string | null
  flag: string
  leagueLogoUrl: string | null
  homeLogoUrl: string | null
  awayLogoUrl: string | null
  homeTeamId: number | null
  awayTeamId: number | null
  time: string
  status: MatchStatus
  minute?: number
  elapsed?: number | null
  score?: [number, number]
  home: string
  away: string
  lambdaHome: number
  lambdaAway: number
  odds: Record<MarketOdds['key'], number>
  pros: TacticalFactor[]
  cons: TacticalFactor[]
  signal: 'STRONG' | 'MODERATE' | 'WEAK'
  keyRisk: string
  summary: string
  referee: Referee
}

export interface TicketLegData {
  flag: string
  match: string
  market: string
  prob: number
  odds: number
  ev: number
}

export interface Ticket {
  mode: Mode
  glyph: string
  combinedOdds: number
  confidence: number
  evAverage: number
  legs: TicketLegData[]
  correlation: string
  correlationPositive: boolean
  analysis: string
  pros: string[]
  cons: string[]
}

/* ------------------------------------------------------------------ */
/* Poisson math                                                        */
/* ------------------------------------------------------------------ */

function factorial(n: number): number {
  let out = 1
  for (let i = 2; i <= n; i++) out *= i
  return out
}

export function poissonPmf(lambda: number, k: number): number {
  return (Math.exp(-lambda) * Math.pow(lambda, k)) / factorial(k)
}

/** Probability mass for 0..(buckets-2) goals plus a final "or more" bucket. */
export function goalDistribution(lambda: number, buckets = 5): number[] {
  const out: number[] = []
  let cumulative = 0
  for (let k = 0; k < buckets - 1; k++) {
    const p = poissonPmf(lambda, k)
    out.push(p)
    cumulative += p
  }
  out.push(Math.max(0, 1 - cumulative))
  return out
}

export interface ScoreLine {
  score: string
  probability: number
}

export interface MatchModel {
  home: number
  draw: number
  away: number
  over25: number
  btts: number
  topScores: ScoreLine[]
  mostLikely: ScoreLine
}

const GRID = 9

export function buildModel(lambdaHome: number, lambdaAway: number): MatchModel {
  if (lambdaHome <= 0 && lambdaAway <= 0) {
    return {
      home: 0, draw: 0, away: 0, over25: 0, btts: 0,
      topScores: [{ score: '--', probability: 0 }],
      mostLikely: { score: '--', probability: 0 },
    }
  }

  let home = 0
  let draw = 0
  let away = 0
  let under25 = 0
  const lines: ScoreLine[] = []

  for (let h = 0; h <= GRID; h++) {
    for (let a = 0; a <= GRID; a++) {
      const p = poissonPmf(lambdaHome, h) * poissonPmf(lambdaAway, a)
      if (h > a) home += p
      else if (h === a) draw += p
      else away += p
      if (h + a <= 2) under25 += p
      lines.push({ score: `${h}-${a}`, probability: p })
    }
  }

  const btts = (1 - Math.exp(-lambdaHome)) * (1 - Math.exp(-lambdaAway))
  const topScores = [...lines].sort((x, y) => y.probability - x.probability).slice(0, 5)

  return {
    home,
    draw,
    away,
    over25: 1 - under25,
    btts,
    topScores,
    mostLikely: topScores[0],
  }
}

/** EV per unit staked: p * (odds - 1) - (1 - p) */
export function expectedValue(probability: number, odds: number): number {
  return probability * (odds - 1) - (1 - probability)
}

export function impliedProbability(odds: number): number {
  return 1 / odds
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`
}

export function signed(value: number, digits = 1): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(digits)}%`
}

export interface MarketRow {
  key: MarketOdds['key']
  label: string
  probability: number
  odds: number
  implied: number
  edge: number
  ev: number
  verdict: 'EV+' | 'MARGINAL' | 'NO EDGE' | 'AVOID'
}

export function marketRows(match: Match, model: MatchModel): MarketRow[] {
  const defs: Array<{ key: MarketOdds['key']; label: string; probability: number }> = [
    { key: 'home', label: 'Gana Local', probability: model.home },
    { key: 'draw', label: 'Empate', probability: model.draw },
    { key: 'away', label: 'Gana Visitante', probability: model.away },
    { key: 'over25', label: 'Mas de 2.5 Goles', probability: model.over25 },
    { key: 'btts', label: 'Ambos Anotan', probability: model.btts },
  ]

  return defs.map((def) => {
    const odds = match.odds[def.key]
    if (odds <= 0) {
      return { ...def, odds: 0, implied: 0, edge: 0, ev: 0, verdict: 'NO EDGE' as const }
    }
    const implied = impliedProbability(odds)
    const edge = def.probability - implied
    const ev = expectedValue(def.probability, odds)
    const verdict: MarketRow['verdict'] =
      edge >= 0.03 ? 'EV+' : edge >= 0 ? 'MARGINAL' : edge >= -0.03 ? 'NO EDGE' : 'AVOID'
    return { ...def, odds, implied, edge, ev, verdict }
  })
}

export function bestOpportunity(rows: MarketRow[]): MarketRow | null {
  const best = [...rows].sort((a, b) => b.edge - a.edge)[0]
  return best && best.edge >= 0.03 ? best : null
}

export const MODE_META: Record<
  Mode,
  { glyph: string; label: string; text: string; border: string; bg: string; accent: string }
> = {
  EDGE: {
    glyph: '⬡',
    label: 'MODO EDGE',
    text: 'text-primary',
    border: 'border-primary/40',
    bg: 'bg-primary/10',
    accent: 'bg-primary',
  },
  VALUE: {
    glyph: '◈',
    label: 'MODO VALUE',
    text: 'text-warning',
    border: 'border-warning/40',
    bg: 'bg-warning/10',
    accent: 'bg-warning',
  },
  BOLD: {
    glyph: '⬟',
    label: 'MODO BOLD',
    text: 'text-negative',
    border: 'border-negative/40',
    bg: 'bg-negative/10',
    accent: 'bg-negative',
  },
}