import type { Mode, Ticket, TicketLegData } from './betmind'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const LEAGUE_FLAGS: Record<string, string> = {
  'Premier League': '\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}',
  'LaLiga': '\u{1F1EA}\u{1F1F8}',
  'Bundesliga': '\u{1F1E9}\u{1F1EA}',
  'Serie A': '\u{1F1EE}\u{1F1F9}',
  'Ligue 1': '\u{1F1EB}\u{1F1F7}',
  'Liga BetPlay': '\u{1F1E8}\u{1F1F4}',
  'Brasileir\u00E3o': '\u{1F1E7}\u{1F1F7}',
  'Serie A (Brazil)': '\u{1F1E7}\u{1F1F7}',
  'Liga Profesional': '\u{1F1E6}\u{1F1F7}',
  'Liga MX': '\u{1F1F2}\u{1F1FD}',
  'MLS': '\u{1F1FA}\u{1F1F8}',
  'Primera Divisi\u00F3n': '\u{1F1E8}\u{1F1F1}',
  'Liga Pro': '\u{1F1EA}\u{1F1E8}',
  'Liga 1': '\u{1F1F5}\u{1F1EA}',
  'Allsvenskan': '\u{1F1F8}\u{1F1EA}',
  'Superliga': '\u{1F1E9}\u{1F1F0}',
  'Super League': '\u{1F1E8}\u{1F1ED}',
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

function flagForLeague(league: string): string {
  return LEAGUE_FLAGS[league] ?? '\u{1F3C1}'
}

function mapLeg(leg: BackendLeg): TicketLegData {
  return {
    flag: flagForLeague(leg.league),
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
      ? 'All selections passed negative-correlation validation'
      : 'Independent selections (no correlation detected)',
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
