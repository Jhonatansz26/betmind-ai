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
}

const UNKNOWN_LEAGUE: LeagueMeta = {
  name: 'Liga Desconocida',
  shortName: 'Desconocida',
  flag: '\u{1F3C1}',
  country: 'Internacional',
  region: 'EUROPE',
}

export const LEAGUE_METADATA: Record<number, LeagueMeta> = {
  // ── AMERICAS ──────────────────────────────────────────────────────────
  239: {
    name: 'Liga BetPlay Dimayor',
    shortName: 'Colombia - BetPlay',
    flag: '\u{1F1E8}\u{1F1F4}',
    country: 'Colombia',
    region: 'AMERICAS',
  },
  71: {
    name: 'Brasileirao Serie A',
    shortName: 'Brasil - Serie A',
    flag: '\u{1F1E7}\u{1F1F7}',
    country: 'Brasil',
    region: 'AMERICAS',
  },
  128: {
    name: 'Liga Profesional Argentina',
    shortName: 'Argentina - Liga Prof.',
    flag: '\u{1F1E6}\u{1F1F7}',
    country: 'Argentina',
    region: 'AMERICAS',
  },
  262: {
    name: 'Liga MX',
    shortName: 'Mexico - Liga MX',
    flag: '\u{1F1F2}\u{1F1FD}',
    country: 'Mexico',
    region: 'AMERICAS',
  },
  253: {
    name: 'Major League Soccer',
    shortName: 'EE.UU. - MLS',
    flag: '\u{1F1FA}\u{1F1F8}',
    country: 'Estados Unidos',
    region: 'AMERICAS',
  },
  274: {
    name: 'Primera Division de Chile',
    shortName: 'Chile - Primera Div.',
    flag: '\u{1F1E8}\u{1F1F1}',
    country: 'Chile',
    region: 'AMERICAS',
  },
  275: {
    name: 'LigaPro Ecuador',
    shortName: 'Ecuador - LigaPro',
    flag: '\u{1F1EA}\u{1F1E8}',
    country: 'Ecuador',
    region: 'AMERICAS',
  },
  294: {
    name: 'Liga 1 Peru',
    shortName: 'Peru - Liga 1',
    flag: '\u{1F1F5}\u{1F1EA}',
    country: 'Peru',
    region: 'AMERICAS',
  },
  9004: {
    name: 'Brasileirao Serie B',
    shortName: 'Brasil - Serie B',
    flag: '\u{1F1E7}\u{1F1F7}',
    country: 'Brasil',
    region: 'AMERICAS',
  },
  9005: {
    name: 'Copa Colombia',
    shortName: 'Colombia - Copa',
    flag: '\u{1F1E8}\u{1F1F4}',
    country: 'Colombia',
    region: 'AMERICAS',
  },
  9011: {
    name: 'CONMEBOL Sudamericana',
    shortName: 'Sudamericana',
    flag: '\u{1F30E}',
    country: 'Sudamerica',
    region: 'AMERICAS',
  },

  // ── EUROPA ────────────────────────────────────────────────────────────
  39: {
    name: 'Premier League',
    shortName: 'Premier',
    flag: '\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}',
    country: 'Inglaterra',
    region: 'EUROPE',
  },
  140: {
    name: 'LaLiga EA Sports',
    shortName: 'LaLiga',
    flag: '\u{1F1EA}\u{1F1F8}',
    country: 'Espana',
    region: 'EUROPE',
  },
  78: {
    name: 'Bundesliga',
    shortName: 'Bundesliga',
    flag: '\u{1F1E9}\u{1F1EA}',
    country: 'Alemania',
    region: 'EUROPE',
  },
  135: {
    name: 'Serie A',
    shortName: 'Serie A',
    flag: '\u{1F1EE}\u{1F1F9}',
    country: 'Italia',
    region: 'EUROPE',
  },
  61: {
    name: 'Ligue 1 McDonald\'s',
    shortName: 'Ligue 1',
    flag: '\u{1F1EB}\u{1F1F7}',
    country: 'Francia',
    region: 'EUROPE',
  },
  113: {
    name: 'Allsvenskan',
    shortName: 'Suecia - Allsvenskan',
    flag: '\u{1F1F8}\u{1F1EA}',
    country: 'Suecia',
    region: 'EUROPE',
  },
  119: {
    name: 'Superliga Danesa',
    shortName: 'Dinamarca - Superliga',
    flag: '\u{1F1E9}\u{1F1F0}',
    country: 'Dinamarca',
    region: 'EUROPE',
  },
  207: {
    name: 'Super League Suiza',
    shortName: 'Suiza - Super League',
    flag: '\u{1F1E8}\u{1F1ED}',
    country: 'Suiza',
    region: 'EUROPE',
  },
  9001: {
    name: 'UEFA Champions League',
    shortName: 'UCL Qualifiers',
    flag: '\u{1F3C6}',
    country: 'Europa',
    region: 'EUROPE',
  },
  9003: {
    name: 'UEFA Conference League',
    shortName: 'UECL Qualifiers',
    flag: '\u{1F3C6}',
    country: 'Europa',
    region: 'EUROPE',
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
    }
  }

  return UNKNOWN_LEAGUE
}
