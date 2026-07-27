/**
 * league-metadata.ts
 *
 * Fuente de verdad única para metadatos de ligas en BetMind AI.
 * Todos los componentes deben usar `resolveLeague()` en lugar de
 * funciones heurísticas ad-hoc de `api.ts`.
 *
 * Indexado por `league_external_id` numérico (mismo que usa API-Football
 * y que está almacenado en la columna `leagues.external_id` de la BD).
 */

export interface LeagueMeta {
  name: string       // Nombre oficial completo — "Liga BetPlay Dimayor"
  shortName: string  // Nombre corto para píldoras y sidebar — "BetPlay"
  flag: string       // Emoji de bandera — "🇨🇴"
  country: string    // País oficial — "Colombia"
  region: 'EUROPE' | 'AMERICAS'
}

/** Fallback cuando el ID es desconocido */
const UNKNOWN_LEAGUE: LeagueMeta = {
  name: 'Liga Desconocida',
  shortName: 'Desconocida',
  flag: '🏁',
  country: 'Internacional',
  region: 'EUROPE',
}

/**
 * Mapa principal indexado por external_id numérico.
 * Cubre los 16 IDs presentes en LEAGUE_ID_MAP de api.ts.
 */
export const LEAGUE_METADATA: Record<number, LeagueMeta> = {
  // ── AMÉRICAS ──────────────────────────────────────────────────────────
  239: {
    name: 'Liga BetPlay Dimayor',
    shortName: 'BetPlay',
    flag: '🇨🇴',
    country: 'Colombia',
    region: 'AMERICAS',
  },
  71: {
    name: 'Brasileirão Série A',
    shortName: 'Brasileirão',
    flag: '🇧🇷',
    country: 'Brasil',
    region: 'AMERICAS',
  },
  128: {
    name: 'Liga Profesional Argentina',
    shortName: 'Liga Pro ARG',
    flag: '🇦🇷',
    country: 'Argentina',
    region: 'AMERICAS',
  },
  262: {
    name: 'Liga MX',
    shortName: 'Liga MX',
    flag: '🇲🇽',
    country: 'México',
    region: 'AMERICAS',
  },
  253: {
    name: 'Major League Soccer',
    shortName: 'MLS',
    flag: '🇺🇸',
    country: 'Estados Unidos',
    region: 'AMERICAS',
  },
  274: {
    name: 'Primera División de Chile',
    shortName: 'Primera CHL',
    flag: '🇨🇱',
    country: 'Chile',
    region: 'AMERICAS',
  },
  275: {
    name: 'LigaPro Ecuador',
    shortName: 'LigaPro ECU',
    flag: '🇪🇨',
    country: 'Ecuador',
    region: 'AMERICAS',
  },
  294: {
    name: 'Liga 1 Perú',
    shortName: 'Liga 1 PER',
    flag: '🇵🇪',
    country: 'Perú',
    region: 'AMERICAS',
  },

  // ── EUROPA ────────────────────────────────────────────────────────────
  39: {
    name: 'Premier League',
    shortName: 'Premier',
    flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    country: 'Inglaterra',
    region: 'EUROPE',
  },
  140: {
    name: 'LaLiga EA Sports',
    shortName: 'LaLiga',
    flag: '🇪🇸',
    country: 'España',
    region: 'EUROPE',
  },
  78: {
    name: 'Bundesliga',
    shortName: 'Bundesliga',
    flag: '🇩🇪',
    country: 'Alemania',
    region: 'EUROPE',
  },
  135: {
    name: 'Serie A',
    shortName: 'Serie A',
    flag: '🇮🇹',
    country: 'Italia',
    region: 'EUROPE',
  },
  61: {
    name: 'Ligue 1 McDonald\'s',
    shortName: 'Ligue 1',
    flag: '🇫🇷',
    country: 'Francia',
    region: 'EUROPE',
  },
  113: {
    name: 'Allsvenskan',
    shortName: 'Allsvenskan',
    flag: '🇸🇪',
    country: 'Suecia',
    region: 'EUROPE',
  },
  119: {
    name: 'Superliga Danesa',
    shortName: 'Superliga DK',
    flag: '🇩🇰',
    country: 'Dinamarca',
    region: 'EUROPE',
  },
  207: {
    name: 'Super League Suiza',
    shortName: 'Super League',
    flag: '🇨🇭',
    country: 'Suiza',
    region: 'EUROPE',
  },
}

/**
 * Resuelve metadatos de liga a partir de su external_id.
 *
 * @param externalId - ID numérico de API-Football (ej: 239 = BetPlay)
 * @param fallbackName - Nombre de texto a usar si el ID no está en el mapa
 * @returns `LeagueMeta` con nombre oficial, bandera y región
 */
export function resolveLeague(
  externalId: number | null | undefined,
  fallbackName?: string,
): LeagueMeta {
  if (externalId != null && LEAGUE_METADATA[externalId]) {
    return LEAGUE_METADATA[externalId]
  }

  // Fallback por nombre cuando el ID no está mapeado
  if (fallbackName) {
    const lower = fallbackName.toLowerCase()
    if (lower.includes('betplay') || lower.includes('colombia'))
      return LEAGUE_METADATA[239]
    if (lower.includes('brasileir') || (lower.includes('serie a') && lower.includes('brazil')))
      return LEAGUE_METADATA[71]
    if (lower.includes('profesional') || lower.includes('argentina'))
      return LEAGUE_METADATA[128]
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
    if (lower.includes('liga mx') || lower.includes('mexico'))
      return LEAGUE_METADATA[262]
    if (lower.includes('mls') || lower.includes('major league'))
      return LEAGUE_METADATA[253]

    // Construir un fallback mínimo con el nombre disponible
    return {
      name: fallbackName,
      shortName: fallbackName.split(' ').slice(0, 2).join(' '),
      flag: '🏁',
      country: 'Internacional',
      region: 'EUROPE',
    }
  }

  return UNKNOWN_LEAGUE
}
