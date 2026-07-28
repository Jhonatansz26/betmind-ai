/**
 * league-metadata.ts
 *
 * Fuente de verdad unica para metadatos de ligas en BetMind AI.
 * Todos los componentes deben usar resolveLeague() en lugar de
 * funciones heuristicas ad-hoc de api.ts.
 *
 * Indexado por league_external_id numerico (mismo que usa API-Football
 * y que esta almacenado en la columna leagues.external_id de la BD).
 */

export interface LeagueMeta {
  name: string
  shortName: string
  flag: string
  country: string
  region: 'EUROPE' | 'AMERICAS'
  logoUrl: string | null
}

const ESPN = (id: string) => `https://a.espncdn.com/i/leaguelogos/soccer/500/${id}.png`
const WIKI = (filename: string) => `https://upload.wikimedia.org/wikipedia/${filename}`

const UNKNOWN_LEAGUE: LeagueMeta = {
  name: 'Liga Desconocida',
  shortName: 'Liga Desconocida',
  flag: '\u{1F3C1}',
  country: 'Internacional',
  region: 'EUROPE',
  logoUrl: null,
}

export const LEAGUE_METADATA: Record<number, LeagueMeta> = {
  // ── AMERICAS ──────────────────────────────────────────────────────────
  239: {
    name: 'Liga BetPlay Dimayor',
    shortName: 'Liga BetPlay Dimayor',
    flag: '\u{1F1E8}\u{1F1F4}',
    country: 'Colombia',
    region: 'AMERICAS',
    logoUrl: ESPN('200'),
  },
  71: {
    name: 'Brasileirao Serie A',
    shortName: 'Brasileirao Serie A',
    flag: '\u{1F1E7}\u{1F1F7}',
    country: 'Brasil',
    region: 'AMERICAS',
    logoUrl: ESPN('85'),
  },
  128: {
    name: 'Liga Profesional Argentina',
    shortName: 'Liga Profesional Argentina',
    flag: '\u{1F1E6}\u{1F1F7}',
    country: 'Argentina',
    region: 'AMERICAS',
    logoUrl: ESPN('1'),
  },
  262: {
    name: 'Liga MX',
    shortName: 'Liga MX',
    flag: '\u{1F1F2}\u{1F1FD}',
    country: 'Mexico',
    region: 'AMERICAS',
    logoUrl: ESPN('22'),
  },
  253: {
    name: 'Major League Soccer',
    shortName: 'Major League Soccer',
    flag: '\u{1F1FA}\u{1F1F8}',
    country: 'Estados Unidos',
    region: 'AMERICAS',
    logoUrl: ESPN('19'),
  },
  274: {
    name: 'Primera Division de Chile',
    shortName: 'Primera Division de Chile',
    flag: '\u{1F1E8}\u{1F1F1}',
    country: 'Chile',
    region: 'AMERICAS',
    logoUrl: ESPN('2329'),
  },
  275: {
    name: 'LigaPro Ecuador',
    shortName: 'LigaPro Ecuador',
    flag: '\u{1F1EA}\u{1F1E8}',
    country: 'Ecuador',
    region: 'AMERICAS',
    logoUrl: ESPN('2344'),
  },
  294: {
    name: 'Liga 1 Peru',
    shortName: 'Liga 1 Peru',
    flag: '\u{1F1F5}\u{1F1EA}',
    country: 'Peru',
    region: 'AMERICAS',
    logoUrl: ESPN('2342'),
  },
  9004: {
    name: 'Brasileirao Serie B',
    shortName: 'Brasileirao Serie B',
    flag: '\u{1F1E7}\u{1F1F7}',
    country: 'Brasil',
    region: 'AMERICAS',
    logoUrl: WIKI('en/thumb/9/94/Campeonato_Brasileiro_Serie_B_logo.svg/200px-Campeonato_Brasileiro_Serie_B_logo.svg.png'),
  },
  9005: {
    name: 'Copa Colombia',
    shortName: 'Copa Colombia',
    flag: '\u{1F1E8}\u{1F1F4}',
    country: 'Colombia',
    region: 'AMERICAS',
    logoUrl: ESPN('200'),
  },
  9010: {
    name: 'CONMEBOL Libertadores',
    shortName: 'CONMEBOL Libertadores',
    flag: '\u{1F30E}',
    country: 'Sudamerica',
    region: 'AMERICAS',
    logoUrl: ESPN('13'),
  },
  9011: {
    name: 'CONMEBOL Sudamericana',
    shortName: 'CONMEBOL Sudamericana',
    flag: '\u{1F30E}',
    country: 'Sudamerica',
    region: 'AMERICAS',
    logoUrl: ESPN('20231'),
  },

  // ── EUROPA ────────────────────────────────────────────────────────────
  39: {
    name: 'Premier League',
    shortName: 'Premier League',
    flag: '\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}',
    country: 'Inglaterra',
    region: 'EUROPE',
    logoUrl: ESPN('23'),
  },
  140: {
    name: 'LaLiga EA Sports',
    shortName: 'LaLiga EA Sports',
    flag: '\u{1F1EA}\u{1F1F8}',
    country: 'Espana',
    region: 'EUROPE',
    logoUrl: ESPN('15'),
  },
  78: {
    name: 'Bundesliga',
    shortName: 'Bundesliga',
    flag: '\u{1F1E9}\u{1F1EA}',
    country: 'Alemania',
    region: 'EUROPE',
    logoUrl: ESPN('10'),
  },
  135: {
    name: 'Serie A',
    shortName: 'Serie A',
    flag: '\u{1F1EE}\u{1F1F9}',
    country: 'Italia',
    region: 'EUROPE',
    logoUrl: ESPN('12'),
  },
  61: {
    name: 'Ligue 1 McDonald\'s',
    shortName: 'Ligue 1 McDonald\'s',
    flag: '\u{1F1EB}\u{1F1F7}',
    country: 'Francia',
    region: 'EUROPE',
    logoUrl: ESPN('9'),
  },
  113: {
    name: 'Allsvenskan',
    shortName: 'Allsvenskan',
    flag: '\u{1F1F8}\u{1F1EA}',
    country: 'Suecia',
    region: 'EUROPE',
    logoUrl: ESPN('65'),
  },
  119: {
    name: 'Superliga Danesa',
    shortName: 'Superliga Danesa',
    flag: '\u{1F1E9}\u{1F1F0}',
    country: 'Dinamarca',
    region: 'EUROPE',
    logoUrl: ESPN('57'),
  },
  207: {
    name: 'Super League Suiza',
    shortName: 'Super League Suiza',
    flag: '\u{1F1E8}\u{1F1ED}',
    country: 'Suiza',
    region: 'EUROPE',
    logoUrl: ESPN('40'),
  },
  9001: {
    name: 'UEFA Champions League',
    shortName: 'UEFA Champions League',
    flag: '\u{1F3C6}',
    country: 'Europa',
    region: 'EUROPE',
    logoUrl: ESPN('2'),
  },
  9002: {
    name: 'UEFA Europa League',
    shortName: 'UEFA Europa League',
    flag: '\u{1F3C6}',
    country: 'Europa',
    region: 'EUROPE',
    logoUrl: ESPN('2310'),
  },
  9003: {
    name: 'UEFA Conference League',
    shortName: 'UEFA Conference League',
    flag: '\u{1F3C6}',
    country: 'Europa',
    region: 'EUROPE',
    logoUrl: WIKI('en/thumb/1/1b/UEFA_Conference_League_logo.svg/200px-UEFA_Conference_League_logo.svg.png'),
  },
}

export function resolveLeague(
  externalId: number | null | undefined,
  fallbackName?: string,
): LeagueMeta {
  if (externalId != null && LEAGUE_METADATA[externalId]) {
    return LEAGUE_METADATA[externalId]
  }

  if (fallbackName) {
    const lower = fallbackName.toLowerCase()
    if (lower.includes('betplay') || (lower.includes('colombia') && lower.includes('liga')))
      return LEAGUE_METADATA[239]
    if (lower.includes('serie a') && lower.includes('brasil'))
      return LEAGUE_METADATA[71]
    if (lower.includes('serie b'))
      return LEAGUE_METADATA[9004]
    if (lower.includes('profesional') || lower.includes('argentina'))
      return LEAGUE_METADATA[128]
    if (lower.includes('copa colombia'))
      return LEAGUE_METADATA[9005]
    if (lower.includes('sudamericana'))
      return LEAGUE_METADATA[9011]
    if (lower.includes('champions league') || lower.includes('ucl'))
      return LEAGUE_METADATA[9001]
    if (lower.includes('conference league') || lower.includes('uecl'))
      return LEAGUE_METADATA[9003]
    if (lower.includes('liga mx') || lower.includes('mexico'))
      return LEAGUE_METADATA[262]
    if (lower.includes('mls') || lower.includes('major league'))
      return LEAGUE_METADATA[253]
    if (lower.includes('premier') || lower.includes('england'))
      return LEAGUE_METADATA[39]
    if (lower.includes('laliga') || lower.includes('spain'))
      return LEAGUE_METADATA[140]
    if (lower.includes('bundesliga') || lower.includes('germany'))
      return LEAGUE_METADATA[78]
    if (lower.includes('ligue 1') || lower.includes('france'))
      return LEAGUE_METADATA[61]
    if (lower.includes('serie a') || lower.includes('italy'))
      return LEAGUE_METADATA[135]

    return {
      name: fallbackName,
      shortName: fallbackName.split(' ').slice(0, 2).join(' '),
      flag: '\u{1F3C1}',
      country: 'Internacional',
      region: 'EUROPE',
      logoUrl: null,
    }
  }

  return UNKNOWN_LEAGUE
}
