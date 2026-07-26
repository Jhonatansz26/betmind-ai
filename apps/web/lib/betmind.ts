// BetMind AI — Poisson model helpers and mock intelligence data.

export type Mode = 'EDGE' | 'VALUE' | 'BOLD'
export type MatchStatus = 'UPCOMING' | 'LIVE' | 'FT'
export type Impact = 'HIGH' | 'MEDIUM' | 'LOW'

export interface League {
  id: string
  name: string
  flag: string
  matches: number
  region: 'EUROPE' | 'AMERICAS'
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
  league: string
  flag: string
  time: string
  status: MatchStatus
  minute?: number
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
    { key: 'home', label: 'Home Win', probability: model.home },
    { key: 'draw', label: 'Draw', probability: model.draw },
    { key: 'away', label: 'Away Win', probability: model.away },
    { key: 'over25', label: 'Over 2.5 Goals', probability: model.over25 },
    { key: 'btts', label: 'BTTS Yes', probability: model.btts },
  ]

  return defs.map((def) => {
    const odds = match.odds[def.key]
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

/* ------------------------------------------------------------------ */
/* Static data                                                         */
/* ------------------------------------------------------------------ */

export const LEAGUES: League[] = [
  { id: 'epl', name: 'Premier League', flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', matches: 3, region: 'EUROPE' },
  { id: 'laliga', name: 'LaLiga', flag: '🇪🇸', matches: 2, region: 'EUROPE' },
  { id: 'bundesliga', name: 'Bundesliga', flag: '🇩🇪', matches: 4, region: 'EUROPE' },
  { id: 'seriea', name: 'Serie A', flag: '🇮🇹', matches: 1, region: 'EUROPE' },
  { id: 'ligue1', name: 'Ligue 1', flag: '🇫🇷', matches: 2, region: 'EUROPE' },
  { id: 'ucl', name: 'UEFA Champions League', flag: '🏆', matches: 0, region: 'EUROPE' },
  { id: 'betplay', name: 'Liga BetPlay', flag: '🇨🇴', matches: 3, region: 'AMERICAS' },
  { id: 'brasileirao', name: 'Brasileirão', flag: '🇧🇷', matches: 5, region: 'AMERICAS' },
  { id: 'profesional', name: 'Liga Profesional', flag: '🇦🇷', matches: 2, region: 'AMERICAS' },
  { id: 'ligamx', name: 'Liga MX', flag: '🇲🇽', matches: 1, region: 'AMERICAS' },
  { id: 'mls', name: 'MLS', flag: '🇺🇸', matches: 3, region: 'AMERICAS' },
]

export const MODE_META: Record<
  Mode,
  { glyph: string; label: string; text: string; border: string; bg: string; accent: string }
> = {
  EDGE: {
    glyph: '⬡',
    label: 'EDGE MODE',
    text: 'text-primary',
    border: 'border-primary/40',
    bg: 'bg-primary/10',
    accent: 'bg-primary',
  },
  VALUE: {
    glyph: '◈',
    label: 'VALUE MODE',
    text: 'text-warning',
    border: 'border-warning/40',
    bg: 'bg-warning/10',
    accent: 'bg-warning',
  },
  BOLD: {
    glyph: '⬟',
    label: 'BOLD MODE',
    text: 'text-negative',
    border: 'border-negative/40',
    bg: 'bg-negative/10',
    accent: 'bg-negative',
  },
}

export const TICKETS: Ticket[] = [
  {
    mode: 'EDGE',
    glyph: '⬡',
    combinedOdds: 1.84,
    confidence: 82,
    evAverage: 0.062,
    legs: [
      {
        flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
        match: 'Arsenal vs Chelsea',
        market: 'Over 1.5 Goals',
        prob: 0.783,
        odds: 1.44,
        ev: 0.041,
      },
      {
        flag: '🇪🇸',
        match: 'Atlético Madrid vs Sevilla',
        market: 'Home Win',
        prob: 0.587,
        odds: 1.72,
        ev: 0.068,
      },
      {
        flag: '🇨🇴',
        match: 'Millonarios vs Nacional',
        market: 'Over 2.5 Goals',
        prob: 0.614,
        odds: 1.85,
        ev: 0.071,
      },
    ],
    correlation: 'Selections are positively correlated',
    correlationPositive: true,
    analysis:
      'Our Poisson model assigns 61.4% probability to Over 2.5 goals in the Bogotá derby, well above the 54.1% implied by the market. Arsenal’s attack index of 1.34 faces a Chelsea back line conceding 1.7 goals per match, which anchors the Over 1.5 leg at 78.3%. The H2H shows 4 of the last 6 meetings exceeded 2.5 goals. Groq analysis flags set-piece efficiency as the primary risk factor across all three legs.',
    pros: [
      'Strong home form across all three fixtures (last 5 matches)',
      'EV confirmed positive on every leg independently',
      'Head-to-head history supports each selection',
    ],
    cons: [
      'Atlético vs Sevilla historically tight and low-scoring',
      'Mid-week fatigue for Arsenal after European travel',
    ],
  },
  {
    mode: 'VALUE',
    glyph: '◈',
    combinedOdds: 2.67,
    confidence: 71,
    evAverage: 0.094,
    legs: [
      {
        flag: '🇩🇪',
        match: 'Bayern Munich vs Dortmund',
        market: 'BTTS Yes',
        prob: 0.672,
        odds: 1.62,
        ev: 0.089,
      },
      {
        flag: '🇮🇹',
        match: 'Inter Milan vs Napoli',
        market: 'Over 2.5 Goals',
        prob: 0.598,
        odds: 1.9,
        ev: 0.102,
      },
      {
        flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
        match: 'Liverpool vs Man City',
        market: 'Over 3.5 Goals',
        prob: 0.441,
        odds: 2.8,
        ev: 0.092,
      },
    ],
    correlation: 'Selections are positively correlated through the goals market',
    correlationPositive: true,
    analysis:
      'All three legs sit on the goals side of the book, where our model consistently prices higher than the market. Der Klassiker has produced BTTS in 8 of the last 10 meetings and the model reads 67.2% against 61.7% implied. Inter and Napoli both average above 1.55 expected goals at home this season. The Liverpool leg is the aggressive component: Over 3.5 carries 44.1% model probability against 35.7% implied, the largest single edge on the board.',
    pros: [
      'Bundesliga averages 3.1 goals per match this season',
      'Both Italian sides rank top-five for shot volume',
      'Rivalry intensity historically drives open, transitional play',
    ],
    cons: [
      'Liverpool vs Man City can turn tactical and low-scoring',
      'Over 3.5 is an aggressive line with high variance',
    ],
  },
  {
    mode: 'BOLD',
    glyph: '⬟',
    combinedOdds: 6.4,
    confidence: 58,
    evAverage: 0.041,
    legs: [
      {
        flag: '🇧🇷',
        match: 'Flamengo vs Palmeiras',
        market: 'Home Win',
        prob: 0.523,
        odds: 2.1,
        ev: 0.038,
      },
      {
        flag: '🇦🇷',
        match: 'River Plate vs Boca Juniors',
        market: 'Over 2.5 Goals',
        prob: 0.497,
        odds: 2.2,
        ev: 0.044,
      },
      {
        flag: '🇲🇽',
        match: 'Club América vs Chivas',
        market: 'BTTS Yes',
        prob: 0.551,
        odds: 2.05,
        ev: 0.042,
      },
      {
        flag: '🇨🇴',
        match: 'Junior vs Santa Fe',
        market: 'Home Win',
        prob: 0.538,
        odds: 1.95,
        ev: 0.04,
      },
    ],
    correlation:
      'All selections are local team favourites in high-intensity domestic fixtures — positively correlated with home crowd effect',
    correlationPositive: true,
    analysis:
      'This is a variance-forward construction. Every leg clears the EV threshold but none exceeds 55% standalone probability, so the ticket lives on the correlation between home advantage and crowd pressure in South American derbies. Referee data supports the read: all four appointments sit above the league average for fouls awarded to the home side. Groq analysis rates the Club América BTTS leg as the most resilient and the River Plate goals line as the most fragile.',
    pros: [
      'All four legs show independently positive expected value',
      'South American derbies favour home teams statistically',
      'Crowd factor measurably amplifies home advantage in these venues',
    ],
    cons: [
      'Higher variance across a four-leg parlay',
      'A single upset collapses the entire ticket',
    ],
  },
]

const REFEREES: Referee[] = [
  {
    name: 'Michael Oliver',
    yellows: 4.1,
    reds: 0.18,
    fouls: 22.4,
    strictness: 68,
    highStakes: 5.2,
    trend: 'Stricter (+0.4 cards)',
  },
  {
    name: 'Daniele Orsato',
    yellows: 5.3,
    reds: 0.24,
    fouls: 26.1,
    strictness: 81,
    highStakes: 6.4,
    trend: 'Stable',
  },
  {
    name: 'Wilmar Roldán',
    yellows: 5.8,
    reds: 0.31,
    fouls: 28.7,
    strictness: 87,
    highStakes: 7.1,
    trend: 'Stricter (+0.7 cards)',
  },
  {
    name: 'Felix Zwayer',
    yellows: 3.6,
    reds: 0.12,
    fouls: 20.8,
    strictness: 54,
    highStakes: 4.4,
    trend: 'Lenient (-0.3 cards)',
  },
]

export const MATCHES: Match[] = [
  {
    id: 'ars-che',
    leagueId: 'epl',
    league: 'Premier League',
    flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    time: '3:00 PM COT',
    status: 'UPCOMING',
    home: 'Arsenal',
    away: 'Chelsea',
    lambdaHome: 1.72,
    lambdaAway: 1.18,
    odds: { home: 1.85, draw: 3.9, away: 4.2, over25: 1.92, btts: 1.78 },
    pros: [
      { category: 'FORM', factor: 'Arsenal unbeaten in last 7 home fixtures', impact: 'HIGH' },
      { category: 'STATISTICS', factor: 'Chelsea concede 1.7 goals per away match', impact: 'HIGH' },
      { category: 'H2H', factor: '4 of last 6 meetings exceeded 2.5 goals', impact: 'MEDIUM' },
    ],
    cons: [
      { category: 'CONTEXT', factor: 'Mid-week European travel for Arsenal', impact: 'MEDIUM' },
      { category: 'REFEREE', factor: 'Oliver trending stricter, disrupts tempo', impact: 'LOW' },
    ],
    signal: 'MODERATE',
    keyRisk: 'Arsenal have rotated their front three in three of the last four league matches.',
    summary:
      'Arsenal generate 1.72 expected goals at home against a Chelsea side that presses high but leaves the half-space between centre-back and full-back exposed. The model favours goals over the outright, with the Over 2.5 line carrying the cleanest edge on the board.',
    referee: REFEREES[0],
  },
  {
    id: 'rma-val',
    leagueId: 'laliga',
    league: 'LaLiga',
    flag: '🇪🇸',
    time: '2:00 PM COT',
    status: 'LIVE',
    minute: 67,
    score: [2, 1],
    home: 'Real Madrid',
    away: 'Valencia',
    lambdaHome: 1.95,
    lambdaAway: 0.92,
    odds: { home: 1.42, draw: 4.8, away: 7.5, over25: 1.7, btts: 1.95 },
    pros: [
      { category: 'STATISTICS', factor: 'Home xG of 1.95, third-highest in LaLiga', impact: 'HIGH' },
      { category: 'FORM', factor: 'Valencia have lost 4 of 5 on the road', impact: 'MEDIUM' },
      { category: 'H2H', factor: 'Real Madrid won 7 of last 8 at the Bernabéu', impact: 'MEDIUM' },
    ],
    cons: [
      { category: 'CONTEXT', factor: 'Live scoreline already priced into the market', impact: 'HIGH' },
      { category: 'REFEREE', factor: 'Low foul count reduces set-piece volume', impact: 'LOW' },
    ],
    signal: 'STRONG',
    keyRisk: 'In-play odds move faster than the model refresh interval on live fixtures.',
    summary:
      'Real Madrid control possession in the middle third and convert territory into shots at an elite rate. Valencia sit deep without a reliable outlet, which suppresses their lambda to 0.92 and keeps the BTTS market unattractive despite the current scoreline.',
    referee: REFEREES[1],
  },
  {
    id: 'bay-bvb',
    leagueId: 'bundesliga',
    league: 'Bundesliga',
    flag: '🇩🇪',
    time: '11:30 AM COT',
    status: 'UPCOMING',
    home: 'Bayern Munich',
    away: 'Borussia Dortmund',
    lambdaHome: 2.05,
    lambdaAway: 1.48,
    odds: { home: 1.72, draw: 4.4, away: 4.0, over25: 1.55, btts: 1.62 },
    pros: [
      { category: 'STATISTICS', factor: 'Bundesliga averages 3.1 goals per match', impact: 'HIGH' },
      { category: 'H2H', factor: 'BTTS landed in 8 of last 10 Klassiker meetings', impact: 'HIGH' },
      { category: 'FORM', factor: 'Dortmund score in 91% of away matches', impact: 'MEDIUM' },
    ],
    cons: [
      { category: 'CONTEXT', factor: 'Rivalry games can start cautiously', impact: 'MEDIUM' },
      { category: 'FORM', factor: 'Bayern rotating goalkeepers', impact: 'LOW' },
    ],
    signal: 'STRONG',
    keyRisk: 'Dortmund have conceded first in six straight away fixtures, which can flatten the game state.',
    summary:
      'Both sides commit full-backs high and neither presses with a compact rest defence. Combined lambda of 3.53 makes this the highest-scoring projection on the board, and the BTTS market is the most efficient way to express it.',
    referee: REFEREES[3],
  },
  {
    id: 'int-nap',
    leagueId: 'seriea',
    league: 'Serie A',
    flag: '🇮🇹',
    time: '1:45 PM COT',
    status: 'UPCOMING',
    home: 'Inter Milan',
    away: 'Napoli',
    lambdaHome: 1.62,
    lambdaAway: 1.34,
    odds: { home: 2.15, draw: 3.4, away: 3.5, over25: 1.9, btts: 1.72 },
    pros: [
      { category: 'STATISTICS', factor: 'Both sides rank top-five for shot volume', impact: 'HIGH' },
      { category: 'FORM', factor: 'Inter scored 2+ in 6 of last 8 at San Siro', impact: 'MEDIUM' },
      { category: 'CONTEXT', factor: 'Title implications push both to attack', impact: 'MEDIUM' },
    ],
    cons: [
      { category: 'H2H', factor: 'Three of last five meetings finished under 2.5', impact: 'MEDIUM' },
      { category: 'REFEREE', factor: 'Orsato among the strictest in Serie A', impact: 'LOW' },
    ],
    signal: 'MODERATE',
    keyRisk: 'Napoli have the discipline to sit in a mid-block and kill the game if they lead early.',
    summary:
      'A genuine top-of-the-table fixture where the model reads 59.8% for Over 2.5 against 52.6% implied. Inter’s lambda of 1.62 is supported by set-piece volume rather than open play, which makes the goals line more resilient than the outright.',
    referee: REFEREES[1],
  },
  {
    id: 'psg-lyo',
    leagueId: 'ligue1',
    league: 'Ligue 1',
    flag: '🇫🇷',
    time: '3:05 PM COT',
    status: 'LIVE',
    minute: 34,
    score: [1, 0],
    home: 'Paris Saint-Germain',
    away: 'Lyon',
    lambdaHome: 1.88,
    lambdaAway: 0.95,
    odds: { home: 1.38, draw: 5.0, away: 8.0, over25: 1.62, btts: 2.0 },
    pros: [
      { category: 'STATISTICS', factor: 'PSG generate 1.88 xG per home match', impact: 'HIGH' },
      { category: 'FORM', factor: 'Lyon winless in 5 away fixtures', impact: 'MEDIUM' },
      { category: 'H2H', factor: 'PSG unbeaten in last 9 at home to Lyon', impact: 'LOW' },
    ],
    cons: [
      { category: 'CONTEXT', factor: 'Market already efficient on the favourite', impact: 'HIGH' },
      { category: 'STATISTICS', factor: 'No market clears the 3% edge threshold', impact: 'HIGH' },
    ],
    signal: 'WEAK',
    keyRisk: 'The book has priced PSG accurately; every line sits inside the model margin of error.',
    summary:
      'A clean model read with no exploitable price. PSG dominate territory and Lyon rarely progress the ball beyond midfield, but the bookmaker margin absorbs the entire edge across all five markets.',
    referee: REFEREES[3],
  },
  {
    id: 'mil-nac',
    leagueId: 'betplay',
    league: 'Liga BetPlay',
    flag: '🇨🇴',
    time: '7:30 PM COT',
    status: 'UPCOMING',
    home: 'Millonarios',
    away: 'Atlético Nacional',
    lambdaHome: 1.42,
    lambdaAway: 1.15,
    odds: { home: 2.2, draw: 3.2, away: 3.4, over25: 2.15, btts: 1.85 },
    pros: [
      { category: 'CONTEXT', factor: 'El Campín altitude suppresses away pressing', impact: 'HIGH' },
      { category: 'FORM', factor: 'Millonarios scored in 11 straight home matches', impact: 'MEDIUM' },
      { category: 'REFEREE', factor: 'Roldán awards 28.7 fouls per match, high set-piece volume', impact: 'MEDIUM' },
    ],
    cons: [
      { category: 'STATISTICS', factor: 'Liga BetPlay averages only 2.3 goals per match', impact: 'MEDIUM' },
      { category: 'H2H', factor: 'Two of last three meetings finished 0-0', impact: 'MEDIUM' },
    ],
    signal: 'MODERATE',
    keyRisk: 'Colombian derbies compress in the final twenty minutes when both sides protect a point.',
    summary:
      'The Bogotá derby projects lower than European fixtures in absolute terms, but the market overcorrects for league scoring averages. At 2.15 the Over 2.5 line carries a meaningful edge against a 61.4% model probability.',
    referee: REFEREES[2],
  },
  {
    id: 'fla-pal',
    leagueId: 'brasileirao',
    league: 'Brasileirão',
    flag: '🇧🇷',
    time: '6:00 PM COT',
    status: 'UPCOMING',
    home: 'Flamengo',
    away: 'Palmeiras',
    lambdaHome: 1.45,
    lambdaAway: 1.12,
    odds: { home: 2.0, draw: 3.3, away: 3.6, over25: 1.85, btts: 1.8 },
    pros: [
      { category: 'CONTEXT', factor: 'Maracanã crowd effect worth 0.2 lambda', impact: 'MEDIUM' },
      { category: 'FORM', factor: 'Flamengo won 4 of last 5 at home', impact: 'MEDIUM' },
      { category: 'H2H', factor: 'Home side won 6 of last 9 in this fixture', impact: 'LOW' },
    ],
    cons: [
      { category: 'STATISTICS', factor: 'Palmeiras concede only 0.9 goals per away match', impact: 'HIGH' },
      { category: 'CONTEXT', factor: 'Squad rotation ahead of Libertadores', impact: 'MEDIUM' },
    ],
    signal: 'WEAK',
    keyRisk: 'Palmeiras defend the box better than any away side in the league, capping the goals ceiling.',
    summary:
      'A tight projection with no standout market. Flamengo hold a modest territorial edge but Palmeiras’ low-block structure keeps both the outright and the goals lines close to fair value.',
    referee: REFEREES[2],
  },
  {
    id: 'ame-chi',
    leagueId: 'ligamx',
    league: 'Liga MX',
    flag: '🇲🇽',
    time: '9:00 PM COT',
    status: 'UPCOMING',
    home: 'Club América',
    away: 'Chivas',
    lambdaHome: 1.55,
    lambdaAway: 1.28,
    odds: { home: 2.05, draw: 3.35, away: 3.5, over25: 1.95, btts: 2.05 },
    pros: [
      { category: 'H2H', factor: 'BTTS landed in 7 of last 10 Clásico Nacional', impact: 'HIGH' },
      { category: 'STATISTICS', factor: 'Chivas score in 78% of away fixtures', impact: 'MEDIUM' },
      { category: 'CONTEXT', factor: 'Derby intensity drives transitional play', impact: 'MEDIUM' },
    ],
    cons: [
      { category: 'FORM', factor: 'América kept three clean sheets in last four', impact: 'MEDIUM' },
      { category: 'REFEREE', factor: 'High card volume can fragment the second half', impact: 'LOW' },
    ],
    signal: 'MODERATE',
    keyRisk: 'A red card in a fixture this heated changes the goal distribution entirely.',
    summary:
      'The Clásico Nacional consistently produces open, error-prone sequences. Combined lambda of 2.83 supports both the goals and BTTS markets, with BTTS at 2.05 offering the better price relative to a 55.1% model probability.',
    referee: REFEREES[2],
  },
]

export const MODEL_HEALTH = {
  brier: 0.19,
  hitRate: 61.3,
  opportunities: 7,
}
