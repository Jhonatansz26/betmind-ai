import type { Mode, Ticket, TicketLegData, Match, MatchStatus, TacticalFactor, Referee, MarketOdds } from './betmind'

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
  return {
    mode,
    glyph: MODE_GLYPHS[mode] ?? '\u{2B21}',
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
): Promise<TicketFetchResult> {
  const body: Record<string, unknown> = {
    modes: modes.map((m) => m.toLowerCase()),
  }
  if (leagueFilter?.length) {
    body.league_filter = leagueFilter
  }

  const res = await fetch(`${API_BASE}/api/v1/tickets/generate`, {
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
  home_team_id: number
  home_team_name: string
  away_team_id: number
  away_team_name: string
  match_date: string
  status: string
  home_score: number | null
  away_score: number | null
  regulation_time_only: boolean
  odds?: {
    home?: number
    draw?: number
    away?: number
    over25?: number
    btts?: number
  }
}

interface BackendMatchesResponse {
  matches: BackendMatch[]
  total: number
}

function mapBackendMatch(raw: BackendMatch): Match {
  const leagueId = LEAGUE_ID_MAP[raw.league_external_id ?? raw.league_id] ?? 'other'
  const leagueName = raw.league_name
  const flag = flagForCountry(raw.league_country, leagueName)

  const statusMap: Record<string, MatchStatus> = {
    SCHEDULED: 'UPCOMING',
    LIVE: 'LIVE',
    INPLAY: 'LIVE',
    FINISHED: 'FT',
    CANCELLED: 'FT',
    POSTPONED: 'UPCOMING',
  }
  const matchStatus = statusMap[raw.status] ?? 'UPCOMING'

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

  return {
    id: String(raw.id),
    leagueId,
    leagueExternalId: raw.league_external_id,
    league: formatCompositeLeagueName(leagueName, raw.league_country),
    leagueCountry: raw.league_country,
    flag,
    time: timeStr,
    status: matchStatus,
    minute: matchStatus === 'LIVE' ? undefined : undefined,
    score: raw.home_score != null && raw.away_score != null ? [raw.home_score, raw.away_score] : undefined,
    home: raw.home_team_name,
    away: raw.away_team_name,
    lambdaHome: 0,
    lambdaAway: 0,
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

export async function fetchMatches(dateStr?: string): Promise<Match[]> {
  const params = new URLSearchParams({
    limit: '200',
    include_upcoming: 'true',
    include_finished: 'false',
  })
  if (dateStr) {
    params.set('date', dateStr)
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

export async function fetchLeagues(): Promise<LeagueData[]> {
  const res = await fetch(`${API_BASE}/api/v1/leagues/`)
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  const data: BackendLeaguesResponse = await res.json()
  return data.leagues
}
