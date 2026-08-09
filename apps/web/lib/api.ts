import type { Mode, Ticket, TicketLegData, Match, MatchStatus, TacticalFactor, Referee, MarketOdds } from './betmind'
import type { BankrollMovement } from './bankroll'
import { resolveLeague } from './league-metadata'
import { formatEV } from './formatters'

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const API_TIMEOUT_MS = 12_000

export interface ApiError {
  code: string
  message: string
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError }

function getStoredAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  const keys = Object.keys(window.localStorage).filter((key) => (
    (key.startsWith('sb-') && key.endsWith('-auth-token'))
    || key === 'betmind_access_token'
  ))
  for (const key of keys) {
    try {
      const value = JSON.parse(window.localStorage.getItem(key) ?? '') as { access_token?: unknown }
      if (typeof value.access_token === 'string' && value.access_token) return value.access_token
    } catch {
      // Ignore unrelated or expired local storage entries.
    }
  }
  return null
}

/** Single HTTP boundary: normalizes transport, timeout and API failures. */
export async function apiFetch<T>(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS)

  try {
    const headers = new Headers(init.headers)
    const token = getStoredAuthToken()
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    if (
      typeof window !== 'undefined'
      && !token
      && window.localStorage.getItem('betmind_dev_is_pro') === 'true'
    ) {
      headers.set('X-Betmind-Dev-Pro', '1')
    }
    const response = await fetch(input, { ...init, headers, signal: controller.signal })
    if (!response.ok) {
      let detail = `No se pudo completar la solicitud (${response.status}).`
      try {
        const body = await response.json() as { detail?: string; message?: string }
        detail = body.detail ?? body.message ?? detail
      } catch {
        // The status is enough when the server did not return JSON.
      }
      return {
        ok: false,
        error: { code: `HTTP_${response.status}`, message: detail },
      }
    }

    return { ok: true, data: await response.json() as T }
  } catch (error) {
    const isTimeout = error instanceof DOMException && error.name === 'AbortError'
    return {
      ok: false,
      error: {
        code: isTimeout ? 'REQUEST_TIMEOUT' : 'NETWORK_ERROR',
        message: isTimeout
          ? 'La solicitud tardó demasiado. Comprueba tu conexión e inténtalo de nuevo.'
          : 'No se pudo conectar con BetMind AI. Comprueba tu conexión e inténtalo de nuevo.',
      },
    }
  } finally {
    clearTimeout(timeout)
  }
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
  xg_home?: number | null
  xg_away?: number | null
  fair_prob?: number | null
  bookmaker_prob?: number | null
  edge?: number | null
  variance_note?: string | null
  reasoning?: string | null
  confidence_score?: number
  match_time_cot: string
}

interface BackendTicket {
  mode: string
  mode_label: string
  legs: BackendLeg[]
  combined_odds: number
  average_ev: number
  kelly_stake?: number | null
  confidence_score: number
  correlation_validated: boolean
  tactical_summary: string
  pros: string[]
  cons: string[]
  staking_suggestion: string
  replacement_candidates?: BackendLeg[]
  optimized_count?: boolean
  original_requested?: number | null
}

interface BackendResponse {
  generated_at: string
  tickets: BackendTicket[]
  total_ev_opportunities: number
  matches_analyzed: number
}

function mapLeg(leg: BackendLeg): TicketLegData {
  return {
    flag: resolveLeague(null, leg.league).flag,
    match: `${leg.home_team} vs ${leg.away_team}`,
    market: leg.market_label,
    prob: leg.our_probability,
    odds: leg.bookmaker_odds,
    ev: leg.expected_value,
    reason: leg.reasoning ?? 'Cuota real comparada contra el modelo Poisson',
    reasoning: leg.reasoning ?? undefined,
    xgHome: leg.xg_home,
    xgAway: leg.xg_away,
    fairProb: leg.fair_prob ?? leg.our_probability,
    bookmakerProb: leg.bookmaker_prob ?? leg.implied_probability,
    edge: leg.edge ?? leg.edge_percentage / 100,
    kellyStake: leg.kelly_stake ?? 0,
    varianceNote: leg.variance_note ?? 'Estadísticamente consistente',
    confidenceScore: leg.confidence_score,
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
    kellyStake: raw.kelly_stake ?? undefined,
    legs: raw.legs.map(mapLeg),
    correlation: raw.correlation_validated
      ? 'Todas las selecciones pasaron la validación de correlación negativa'
      : 'Selecciones independientes (sin correlación detectada)',
    correlationPositive: raw.correlation_validated,
    analysis: raw.tactical_summary,
    pros: raw.pros,
    cons: raw.cons,
    rationale: [
      'Modelo Poisson calibrado',
      `${formatEV(raw.average_ev)} EV medio`,
      `${raw.confidence_score}% de confianza del modelo`,
      raw.correlation_validated
        ? 'Validación de correlación negativa superada'
        : 'Selecciones independientes, sin correlación detectada',
    ],
    optimizedCount: raw.optimized_count,
    originalRequested: raw.original_requested,
    replacementCandidates: raw.replacement_candidates?.map(mapLeg) ?? [],
  }
}

export interface TicketFetchResult {
  tickets: Ticket[]
  totalEvOpportunities: number
  matchesAnalyzed: number
  generatedAt: string
}

export type SavedTicketStatus = 'PENDING' | 'WON' | 'LOST' | 'VOID'

export interface SavedTicketRecord {
  id: number
  ticket_data: Ticket
  status: SavedTicketStatus
  total_odds: number
  total_ev: number
  stake_amount?: number | null
  created_at: string
  bankroll_movement?: BankrollMovement | null
}

export async function saveTicket(
  ticket: Ticket,
  stakeAmount?: number | null,
): Promise<ApiResult<SavedTicketRecord>> {
  return apiFetch<SavedTicketRecord>(`${API_BASE}/api/v1/tickets/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticket_data: ticket,
      total_odds: ticket.combinedOdds,
      total_ev: ticket.evAverage,
      ...(stakeAmount != null ? { stake_amount: stakeAmount } : {}),
    }),
  })
}

export interface ClaimTicketsResponse {
  claimed_count: number
  claimed_ticket_ids: number[]
  message: string
}

export async function claimAnonymousTickets(ticketIds: number[]): Promise<ApiResult<ClaimTicketsResponse>> {
  return apiFetch<ClaimTicketsResponse>(`${API_BASE}/api/v1/tickets/claim`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket_ids: ticketIds }),
  })
}

export async function fetchTicketHistory(): Promise<ApiResult<SavedTicketRecord[]>> {
  return apiFetch<SavedTicketRecord[]>(`${API_BASE}/api/v1/tickets/history`)
}

export async function updateTicketStatus(
  ticketId: number,
  status: SavedTicketStatus,
): Promise<ApiResult<SavedTicketRecord>> {
  return apiFetch<SavedTicketRecord>(`${API_BASE}/api/v1/tickets/${ticketId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

export async function fetchTickets(
  modes: Mode[] = ['EDGE', 'VALUE', 'BOLD'],
  leagueKeys?: string[],
  dateFilter?: string,
  selectionCount?: number,
  markets?: string[],
): Promise<ApiResult<TicketFetchResult>> {
  const url = new URL(`${API_BASE}/api/v1/tickets/generate`)
  if (dateFilter) {
    url.searchParams.set('date_filter', dateFilter)
  }

  const body: Record<string, unknown> = {
    modes: modes.map((m) => m.toLowerCase()),
  }
  if (leagueKeys?.length) {
    body.league_keys = leagueKeys
  }
  if (selectionCount) body.selection_count = selectionCount
  if (markets?.length) body.markets = markets

  const result = await apiFetch<BackendResponse>(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!result.ok) return result
  const data = result.data

  return { ok: true, data: {
    tickets: data.tickets.map(mapBackendTicket),
    totalEvOpportunities: data.total_ev_opportunities,
    matchesAnalyzed: data.matches_analyzed,
    generatedAt: data.generated_at,
  } }
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
  match_type: string
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
  match_advanced_stats?: Match['advancedStats']
  referee_profile?: Match['refereeProfile']
}

interface BackendMatchesResponse {
  matches: BackendMatch[]
  total: number
}

function mapBackendMatch(raw: BackendMatch): Match {
  const leagueId = String(raw.league_external_id ?? raw.league_id ?? 'other')
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
    league: leagueName,
    leagueCountry: raw.league_country,
    matchType: raw.match_type ?? 'LEAGUE',
    flag,
    leagueLogoUrl,
    homeLogoUrl: raw.home_team_logo_url,
    awayLogoUrl: raw.away_team_logo_url,
    homeTeamId: raw.home_team_id,
    awayTeamId: raw.away_team_id,
    time: timeStr,
    matchDate: raw.match_date,
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
    advancedStats: raw.match_advanced_stats ?? null,
    refereeProfile: raw.referee_profile ?? null,
  }
}

export async function fetchMatches(dateFilter?: string): Promise<ApiResult<Match[]>> {
  const params = new URLSearchParams({
    limit: '200',
    include_upcoming: 'true',
    include_finished: 'true',
  })
  if (dateFilter) {
    params.set('date_filter', dateFilter)
  }

  const result = await apiFetch<BackendMatchesResponse>(`${API_BASE}/api/v1/matches/?${params.toString()}`)
  if (!result.ok) return result
  return { ok: true, data: dedupeMatches(result.data.matches.map(mapBackendMatch)) }
}

const DEDUP_WINDOW_MS = 2 * 60 * 60 * 1000
const DEDUP_SIMILARITY_THRESHOLD = 0.85

/** Normalización de nombre de equipo para comparar variantes cross-provider:
 *  tildes, mayúsculas, puntuación y abreviaciones comunes (Independ. → Independiente). */
function normalizeTeamName(name: string): string {
  const expanded: Record<string, string> = {
    independ: 'independiente',
    jrs: 'juniors',
    'st.': 'saint',
    fc: '',
    cf: '',
    if: '',
    ff: '',
    bk: '',
    aif: '',
  }
  const cleaned = name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[()]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((token) => (token in expanded ? expanded[token] : token))
    .filter(Boolean)
    .join(' ')
  return cleaned.trim()
}

function teamNameSimilarity(a: string, b: string): number {
  const na = normalizeTeamName(a)
  const nb = normalizeTeamName(b)
  if (!na || !nb) return 0
  if (na === nb) return 1
  const tokensA = new Set(na.split(' '))
  const tokensB = new Set(nb.split(' '))
  let intersection = 0
  for (const t of tokensA) if (tokensB.has(t)) intersection++
  const union = tokensA.size + tokensB.size - intersection
  return union === 0 ? 0 : intersection / union
}

/** Clave por liga + nombres normalizados (no por IDs, que difieren entre proveedores). */
function matchKey(match: Match): string {
  return `${match.leagueExternalId ?? match.leagueId}|${normalizeTeamName(match.home)}|${normalizeTeamName(match.away)}`
}

function matchRichness(match: Match): number {
  let score = 0
  if (match.lambdaHome > 0 || match.lambdaAway > 0) score += 4
  if (match.odds && (match.odds.home > 0 || match.odds.draw > 0 || match.odds.away > 0)) score += 2
  if (match.score) score += 1
  return score
}

function sameTwoHourWindow(a: Match, b: Match): boolean {
  const timeA = new Date(a.matchDate).getTime()
  const timeB = new Date(b.matchDate).getTime()
  if (isNaN(timeA) || isNaN(timeB)) return false
  return Math.abs(timeA - timeB) < DEDUP_WINDOW_MS
}

/** Similitud de pareja de equipos (home vs home AND away vs away >= 0.85). */
function sameTeamPair(a: Match, b: Match): boolean {
  return (
    teamNameSimilarity(a.home, b.home) >= DEDUP_SIMILARITY_THRESHOLD &&
    teamNameSimilarity(a.away, b.away) >= DEDUP_SIMILARITY_THRESHOLD
  )
}

function dedupeMatches(matches: Match[]): Match[] {
  const byKey = new Map<string, Match[]>()
  for (const match of matches) {
    const key = matchKey(match)
    const bucket = byKey.get(key) ?? []
    const twin = bucket.find((existing) => sameTwoHourWindow(existing, match))
    if (twin) {
      // Misma pareja (nombres normalizados) en ventana de 2h: conservar el más rico
      if (matchRichness(match) > matchRichness(twin)) {
        byKey.set(key, bucket.map((m) => (m === twin ? match : m)))
      }
    } else {
      // Backstop: pareja con nombres distintos pero similitud >= 0.85 (ej.
      // "Independ. Rivadavia" vs "Independiente Rivadavia" del mismo encuentro)
      const fuzzyTwin = bucket.find((existing) => sameTeamPair(existing, match))
      if (fuzzyTwin && sameTwoHourWindow(fuzzyTwin, match)) {
        if (matchRichness(match) > matchRichness(fuzzyTwin)) {
          byKey.set(key, bucket.map((m) => (m === fuzzyTwin ? match : m)))
        }
      } else {
        // Misma pareja pero distinto horario: partidos legítimamente distintos
        bucket.push(match)
        byKey.set(key, bucket)
      }
    }
  }
  return Array.from(byKey.values())
    .flat()
    .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime())
}

export interface LeagueData {
  key: string
  group?: string
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

export async function fetchLeagues(targetDate?: string): Promise<ApiResult<LeagueData[]>> {
  const params = targetDate ? `?date=${targetDate}` : ""
  const result = await apiFetch<BackendLeaguesResponse>(`${API_BASE}/api/v1/leagues/${params}`)
  if (!result.ok) return result
  return { ok: true, data: result.data.leagues }
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

export interface MatchFormRecord {
  match_id: number
  match_date: string
  home_team: string
  away_team: string
  home_score: number | null
  away_score: number | null
  result: 'W' | 'D' | 'L'
}

export interface MatchH2HRecord {
  id: number
  match_date: string
  home_team: string
  away_team: string
  home_score: number | null
  away_score: number | null
  status: string
  events: Array<{
    event_type: string
    minute: number
    added_time: number
    is_home: boolean | null
    player_name: string | null
  }>
}

export interface MatchH2HData {
  match_id: number
  total: number
  h2h: MatchH2HRecord[]
  home_form: MatchFormRecord[]
  away_form: MatchFormRecord[]
}

export async function fetchMatchH2H(matchId: string): Promise<ApiResult<MatchH2HData>> {
  return apiFetch<MatchH2HData>(`${API_BASE}/api/v1/matches/${matchId}/h2h`)
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

export async function fetchMatchPrediction(matchId: string): Promise<ApiResult<EnrichedMatch | null>> {
  const matchUrl = `${API_BASE}/api/v1/matches/${matchId}`
  const predUrl = `${API_BASE}/api/v1/predictions/${matchId}`

  const [matchResult, predictionResult] = await Promise.all([
    apiFetch<BackendMatch>(matchUrl),
    apiFetch<BackendPrediction>(predUrl),
  ])

  if (!matchResult.ok) return matchResult
  const baseMatch = mapBackendMatch(matchResult.data)

  if (!predictionResult.ok) {
    return {
      ok: true,
      data: {
        ...baseMatch,
        probabilities: { home_win: 0, draw: 0, away_win: 0, over_2_5: 0, over_1_5: 0 },
        evAnalysis: [], confidenceScore: 0, riskLevel: 'MEDIUM',
        tacticalNarrative: '', tacticalHeadline: '', llmModelUsed: 'none',
        tacticalAnalysis: null, betBuilder: [],
      },
    }
  }

  return { ok: true, data: mapBackendPrediction(predictionResult.data, baseMatch) }
}
