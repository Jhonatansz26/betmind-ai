import type { Mode, Ticket, TicketLegData, Match, MatchStatus, TacticalFactor, Referee, MarketOdds } from './betmind'
import { resolveLeague } from './league-metadata'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const COUNTRY_ISO: Record<string, string> = {
  'England': 'GB-ENG',
  'Spain': 'ES',
  'Germany': 'DE',
  'Italy': 'IT',
  'France': 'FR',
  'Colombia': 'CO',
  'Brazil': 'BR',
  'Argentina': 'AR',
  'Mexico': 'MX',
  'USA': 'US',
  'Chile': 'CL',
  'Ecuador': 'EC',
  'Peru': 'PE',
  'Sweden': 'SE',
  'Denmark': 'DK',
  'Switzerland': 'CH',
  'Portugal': 'PT',
}

export function isoToFlagEmoji(code: string): string {
  if (code === 'GB-ENG') return '\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}'
  return code
    .toUpperCase()
    .split('')
    .map((c) => String.fromCodePoint(0x1F1E6 - 65 + c.charCodeAt(0)))
    .join('')
}

/**
 * @deprecated Use `resolveLeague()` from `@/lib/league-metadata` instead.
 * Kept for backward compatibility with components not yet migrated.
 */
export function flagForCountry(country: string | null | undefined, fallbackLeague?: string): string {
  if (country && COUNTRY_ISO[country]) {
    return isoToFlagEmoji(COUNTRY_ISO[country])
  }
  if (fallbackLeague) {
    if (fallbackLeague.includes('Premier League') || fallbackLeague === 'England') return isoToFlagEmoji('GB-ENG')
    if (fallbackLeague.includes('LaLiga') || fallbackLeague.includes('Spain')) return isoToFlagEmoji('ES')
    if (fallbackLeague.includes('Bundesliga') || fallbackLeague.includes('Germany')) return isoToFlagEmoji('DE')
    if (fallbackLeague.includes('Ligue 1') || fallbackLeague.includes('France')) return isoToFlagEmoji('FR')
    if (fallbackLeague.includes('BetPlay') || fallbackLeague.includes('Colombia')) return isoToFlagEmoji('CO')
    if (fallbackLeague.includes('Serie A') && fallbackLeague.includes('Brazil')) return isoToFlagEmoji('BR')
    if (fallbackLeague.includes('Brazil') || fallbackLeague.includes('Brasileir')) return isoToFlagEmoji('BR')
    if (fallbackLeague.includes('Profesional') || fallbackLeague.includes('Argentina')) return isoToFlagEmoji('AR')
    if (fallbackLeague.includes('MX') || fallbackLeague.includes('Mexico')) return isoToFlagEmoji('MX')
    if (fallbackLeague.includes('MLS') || fallbackLeague.includes('Major League Soccer') || fallbackLeague.includes('USA')) return isoToFlagEmoji('US')
    if (fallbackLeague.includes('Serie A')) return isoToFlagEmoji('IT')
  }
  return '\u{1F3C1}'
}

/**
 * @deprecated Use `resolveLeague()` from `@/lib/league-metadata` instead.
 * Kept for backward compatibility with components not yet migrated.
 */
export function formatCompositeLeagueName(name: string, country?: string | null): string {
  if (country) {
    if (name.toLowerCase().includes(country.toLowerCase())) {
      return name
    }
    return `${name} · ${country}`
  }
  if (name === 'Serie A') return 'Serie A · Italia'
  return name
}

export const LEAGUE_ID_MAP: Record<number, string> = {
  39: 'epl',
  140: 'laliga',
  78: 'bundesliga',
  135: 'seriea',
  61: 'ligue1',
  239: 'betplay',
  71: 'brasileirao',
  128: 'profesional',
  262: 'ligamx',
  253: 'mls',
  274: 'primera_chile',
  275: 'liga_pro_ecu',
  294: 'liga_1_peru',
  113: 'allsvenskan',
  119: 'superliga_den',
  207: 'super_league_sui',
}

const MODE_GLYPHS: Record<Mode, string> = {
  EDGE: '\u{2B21}',
  VALUE: '\u{25C8}',
  BOLD: '\u{2B1F}',
}

interface BackendLeg {
  match_id: number
  home_team: string
  away_team: string
  league: string
  market_name: string
  market_label: string
  our_probability: number
  bookmaker_odds: number
  implied_probability: number
  edge_percentage: number
  expected_value: number
  kelly_stake?: number
  match_time_cot: string
}

interface BackendTicket {
  mode: string
  mode_label: string
  legs: BackendLeg[]
  combined_odds: number
  average_ev: number
  confidence_score: number
  correlation_validated: boolean
  tactical_summary: string
  pros: string[]
  cons: string[]
  staking_suggestion: string
}

interface BackendResponse {
  generated_at: string
  tickets: BackendTicket[]
  total_ev_opportunities: number
  matches_analyzed: number
}

function mapLeg(leg: BackendLeg): TicketLegData {
  return {
    flag: flagForCountry(null, leg.league),
    match: `${leg.home_team} vs ${leg.away_team}`,
    market: leg.market_label,
    prob: leg.our_probability,
    odds: leg.bookmaker_odds,
    ev: leg.expected_value,
  }
}

function mapBackendTicket(raw: BackendTicket): Ticket {
  const mode = raw.mode.toUpperCase() as Mode
  const validMode: Mode = ['EDGE', 'VALUE', 'BOLD'].includes(mode) ? mode : 'EDGE'
  return {
    mode: validMode,
    glyph: MODE_GLYPHS[validMode] ?? '\u{2B21}',
    combinedOdds: raw.combined_odds,
    confidence: raw.confidence_score,
    evAverage: raw.average_ev,
    legs: raw.legs.map(mapLeg),
    correlation: raw.correlation_validated
      ? 'Todas las selecciones pasaron la validación de correlación negativa'
      : 'Selecciones independientes (sin correlación detectada)',
    correlationPositive: raw.correlation_validated,
    analysis: raw.tactical_summary,
    pros: raw.pros,
    cons: raw.cons,
  }
}

export interface TicketFetchResult {
  tickets: Ticket[]
  totalEvOpportunities: number
  matchesAnalyzed: number
  generatedAt: string
}

export async function fetchTickets(
  modes: Mode[] = ['EDGE', 'VALUE', 'BOLD'],
  leagueFilter?: string[],
  dateFilter?: string,
): Promise<TicketFetchResult> {
  const url = new URL(`${API_BASE}/api/v1/tickets/generate`)
  if (dateFilter) {
    url.searchParams.set('date_filter', dateFilter)
  }

  const body: Record<string, unknown> = {
    modes: modes.map((m) => m.toLowerCase()),
  }
  if (leagueFilter?.length) {
    body.league_filter = leagueFilter
  }

  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }

  const data: BackendResponse = await res.json()

  return {
    tickets: data.tickets.map(mapBackendTicket),
    totalEvOpportunities: data.total_ev_opportunities,
    matchesAnalyzed: data.matches_analyzed,
    generatedAt: data.generated_at,
  }
}

interface BackendMatch {
  id: number
  external_id: number
  league_id: number
  league_name: string
  league_external_id: number | null
  league_country: string | null
  league_logo_url: string | null
  home_team_id: number
  home_team_name: string
  home_team_logo_url: string | null
  away_team_id: number
  away_team_name: string
  away_team_logo_url: string | null
  match_date: string
  status: string
  home_score: number | null
  away_score: number | null
  regulation_time_only: boolean
  minute?: number | null
  odds?: {
    home?: number
    draw?: number
    away?: number
    over25?: number
    btts?: number
  }
  prediction?: {
    prediction_type: string
    confidence: string
    value_score: number
    reasoning: string | null
    lambda_home: number | null
    lambda_away: number | null
  } | null
}

interface BackendMatchesResponse {
  matches: BackendMatch[]
  total: number
}

function mapBackendMatch(raw: BackendMatch): Match {
  const leagueId = LEAGUE_ID_MAP[raw.league_external_id ?? raw.league_id] ?? 'other'
  const leagueMeta = resolveLeague(raw.league_external_id, raw.league_name)
  const leagueName = leagueMeta.name
  const flag = leagueMeta.flag
  const leagueLogoUrl = raw.league_logo_url || leagueMeta.logoUrl

  const statusMap: Record<string, MatchStatus> = {
    // API-Football short codes
    '1H': 'IN_PLAY',
    '2H': 'IN_PLAY',
    HT: 'PAUSED',
    ET: 'IN_PLAY',
    BT: 'PAUSED',
    P: 'PAUSED',
    NS: 'SCHEDULED',
    TBD: 'SCHEDULED',
    PST: 'FINISHED',
    POST: 'FINISHED',
    // Long form codes
    SCHEDULED: 'SCHEDULED',
    LIVE: 'IN_PLAY',
    INPLAY: 'IN_PLAY',
    IN_PLAY: 'IN_PLAY',
    FIRST_HALF: 'IN_PLAY',
    SECOND_HALF: 'IN_PLAY',
    HALF_TIME: 'PAUSED',
    PAUSED: 'PAUSED',
    SUSPENDED: 'PAUSED',
    INTERRUPTED: 'PAUSED',
    FINISHED: 'FINISHED',
    FT: 'FINISHED',
    AET: 'FINISHED',
    PEN: 'FINISHED',
    CANCELLED: 'FINISHED',
    POSTPONED: 'SCHEDULED',
    ABANDONED: 'FINISHED',
    NOT_STARTED: 'SCHEDULED',
    UPCOMING: 'SCHEDULED',
  }
  let matchStatus = statusMap[raw.status] ?? statusMap[raw.status?.toUpperCase()] ?? 'SCHEDULED'

  const matchDate = new Date(raw.match_date)
  const cotTime = matchDate.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'America/Bogota',
  })
  const timeStr = `${cotTime} COT`

  const defaultReferee: Referee = {
    name: 'Por confirmar',
    yellows: 0,
    reds: 0,
    fouls: 0,
    strictness: 0,
    highStakes: 0,
    trend: 'N/D',
  }

  const realOdds = raw.odds ?? { home: undefined, draw: undefined, away: undefined, over25: undefined, btts: undefined }
  const prediction = raw.prediction ?? null

  // Score: 0 is valid, only null/undefined means "no score data"
  const homeScoreRaw = raw.home_score
  const awayScoreRaw = raw.away_score
  const homeScoreNum = typeof homeScoreRaw === 'number' ? homeScoreRaw
    : typeof homeScoreRaw === 'string' ? parseFloat(homeScoreRaw) : null
  const awayScoreNum = typeof awayScoreRaw === 'number' ? awayScoreRaw
    : typeof awayScoreRaw === 'string' ? parseFloat(awayScoreRaw) : null
  const hasScores = typeof homeScoreNum === 'number' && !isNaN(homeScoreNum)
    && typeof awayScoreNum === 'number' && !isNaN(awayScoreNum)

  return {
    id: String(raw.id),
    leagueId,
    leagueExternalId: raw.league_external_id,
    league: formatCompositeLeagueName(leagueName, raw.league_country),
    leagueCountry: raw.league_country,
    flag,
    leagueLogoUrl,
    homeLogoUrl: raw.home_team_logo_url,
    awayLogoUrl: raw.away_team_logo_url,
    homeTeamId: raw.home_team_id,
    awayTeamId: raw.away_team_id,
    time: timeStr,
    status: matchStatus,
    minute: matchStatus === 'IN_PLAY' || matchStatus === 'PAUSED' ? (raw.minute ?? undefined) : undefined,
    elapsed: raw.minute ?? null,
    score: hasScores ? [homeScoreNum as number, awayScoreNum as number] : undefined,
    home: raw.home_team_name || 'Local',
    away: raw.away_team_name || 'Visitante',
    lambdaHome: prediction?.lambda_home ?? 0,
    lambdaAway: prediction?.lambda_away ?? 0,
    odds: {
      home: realOdds.home ?? 0,
      draw: realOdds.draw ?? 0,
      away: realOdds.away ?? 0,
      over25: realOdds.over25 ?? 0,
      btts: realOdds.btts ?? 0,
    },
    pros: [],
    cons: [],
    signal: 'WEAK' as const,
    keyRisk: '',
    summary: `${raw.home_team_name} vs ${raw.away_team_name} — ${leagueName}`,
    referee: defaultReferee,
  }
}

export async function fetchMatches(dateFilter?: string): Promise<Match[]> {
  const params = new URLSearchParams({
    limit: '200',
    include_upcoming: 'true',
    include_finished: 'true',
  })
  if (dateFilter) {
    params.set('date_filter', dateFilter)
  }

  const res = await fetch(`${API_BASE}/api/v1/matches/?${params.toString()}`)

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }

  const data: BackendMatchesResponse = await res.json()
  return data.matches.map(mapBackendMatch)
}

export interface LeagueData {
  id: number
  external_id: number
  name: string
  country: string | null
  logo_url: string | null
  tier: string | null
  active_matches: number
}

interface BackendLeaguesResponse {
  leagues: LeagueData[]
  total: number
}

export async function fetchLeagues(targetDate?: string): Promise<LeagueData[]> {
  const params = targetDate ? `?date=${targetDate}` : ""
  const res = await fetch(`${API_BASE}/api/v1/leagues/${params}`)
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  const data: BackendLeaguesResponse = await res.json()
  return data.leagues
}

/* ------------------------------------------------------------------ */
/* Prediction endpoint                                                  */
/* ------------------------------------------------------------------ */

interface BackendEVEntry {
  market: string
  our_probability: number
  bookmaker_implied_probability: number | null
  bookmaker_odds: number | null
  edge_percentage: number | null
  expected_value: number | null
  kelly_stake: number | null
  verdict: string
}

interface BackendTacticalAnalysis {
  match_id: number
  model_version: string
  goals_narrative: Record<string, unknown> | null
  cards_narrative: Record<string, unknown> | null
  corners_narrative: Record<string, unknown> | null
  player_props_narratives: Record<string, unknown>[]
  bet_builder_suggestions: Record<string, unknown>[]
  overall_confidence: number
  match_preview_headline: string
  llm_model_used: string
  data_completeness_score: number
}

interface BackendPrediction {
  match_id: number
  home_team: string
  away_team: string
  league: string
  match_date: string
  lambda_home: number
  lambda_away: number
  probabilities: {
    home_win: number
    draw: number
    away_win: number
    over_2_5: number
    over_1_5: number
  }
  ev_analysis: BackendEVEntry[]
  confidence_score: number
  tactical_narrative: string
  tactical_analysis: BackendTacticalAnalysis | null
  confidence_level: string
  risk_level: string
  bet_builder: Array<{
    profile: string
    label: string
    selections: Array<{
      market_name: string
      label: string
      probability: number
      odds_estimate: number
    }>
    combined_odds: number
    combined_probability: number
  }>
}

export interface EnrichedMatch extends Match {
  probabilities: {
    home_win: number
    draw: number
    away_win: number
    over_2_5: number
    over_1_5: number
  }
  evAnalysis: Array<{
    market: string
    probability: number
    odds: number
    edge: number
    ev: number
    verdict: string
  }>
  confidenceScore: number
  riskLevel: string
  tacticalNarrative: string
  tacticalHeadline: string
  llmModelUsed: string
  tacticalAnalysis: {
    goals_narrative: Record<string, unknown> | null
    cards_narrative: Record<string, unknown> | null
    corners_narrative: Record<string, unknown> | null
    overall_confidence: number
    data_completeness_score: number
  } | null
  betBuilder: Array<{
    profile: string
    label: string
    selections: Array<{
      market_name: string
      label: string
      probability: number
      odds_estimate: number
    }>
    combined_odds: number
    combined_probability: number
  }>
}

function mapBackendPrediction(raw: BackendPrediction, baseMatch: Match): EnrichedMatch {
  return {
    ...baseMatch,
    lambdaHome: raw.lambda_home,
    lambdaAway: raw.lambda_away,
    probabilities: {
      home_win: raw.probabilities.home_win,
      draw: raw.probabilities.draw,
      away_win: raw.probabilities.away_win,
      over_2_5: raw.probabilities.over_2_5,
      over_1_5: raw.probabilities.over_1_5,
    },
    evAnalysis: raw.ev_analysis.map((ev) => ({
      market: ev.market,
      probability: ev.our_probability,
      odds: ev.bookmaker_odds ?? 0,
      edge: ev.edge_percentage ?? 0,
      ev: ev.expected_value ?? 0,
      verdict: ev.verdict,
    })),
    confidenceScore: raw.confidence_score,
    riskLevel: raw.risk_level ?? 'MEDIUM',
    tacticalNarrative: raw.tactical_narrative,
    tacticalHeadline: raw.tactical_analysis?.match_preview_headline ?? '',
    llmModelUsed: raw.tactical_analysis?.llm_model_used ?? 'none',
    tacticalAnalysis: raw.tactical_analysis ? {
      goals_narrative: raw.tactical_analysis.goals_narrative,
      cards_narrative: raw.tactical_analysis.cards_narrative,
      corners_narrative: raw.tactical_analysis.corners_narrative,
      overall_confidence: raw.tactical_analysis.overall_confidence,
      data_completeness_score: raw.tactical_analysis.data_completeness_score,
    } : null,
    betBuilder: raw.bet_builder ?? [],
  }
}

export async function fetchMatchPrediction(matchId: string): Promise<EnrichedMatch | null> {
  const matchUrl = `${API_BASE}/api/v1/matches/${matchId}`
  const predUrl = `${API_BASE}/api/v1/predictions/${matchId}`

  console.log(`[fetchMatchPrediction] Loading match ${matchId}`)

  const [matchRes, predRes] = await Promise.allSettled([
    fetch(matchUrl),
    fetch(predUrl),
  ])

  if (matchRes.status === 'rejected') {
    throw new Error(`Match API error: ${matchRes.reason}`)
  }

  if (!matchRes.value.ok) {
    console.warn(`[fetchMatchPrediction] Match not found (HTTP ${matchRes.value.status}), returning null`)
    return null
  }

  const matchData = await matchRes.value.json()
  const baseMatch = mapBackendMatch(matchData)

  if (predRes.status === 'rejected' || !predRes.value.ok) {
    console.warn(
      `[fetchMatchPrediction] Prediction not available for match ${matchId} ` +
      `(HTTP ${predRes.status === 'rejected' ? 'REJECTED' : predRes.value.status}). ` +
      `Returning base match — prediction data is insufficient or unavailable.`
    )
    return {
      ...baseMatch,
      lambdaHome: baseMatch.lambdaHome,
      lambdaAway: baseMatch.lambdaAway,
      probabilities: { home_win: 0, draw: 0, away_win: 0, over_2_5: 0, over_1_5: 0 },
      evAnalysis: [],
      confidenceScore: 0,
      riskLevel: 'MEDIUM',
      tacticalNarrative: '',
      tacticalHeadline: '',
      llmModelUsed: 'none',
      tacticalAnalysis: null,
      betBuilder: [],
    }
  }

  const predData: BackendPrediction = await predRes.value.json()
  console.log(
    `[fetchMatchPrediction] Prediction loaded: lambda_home=${predData.lambda_home}, ` +
    `lambda_away=${predData.lambda_away}, ` +
    `confidence=${predData.confidence_score}, ` +
    `llm=${predData.tactical_analysis?.llm_model_used ?? 'none'}`
  )
  return mapBackendPrediction(predData, baseMatch)
}
