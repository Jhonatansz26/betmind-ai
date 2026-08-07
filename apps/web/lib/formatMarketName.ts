import { formatDecimal } from './formatters'

const EXACT_NAMES: Record<string, string> = {
  double_1x: 'Doble Oportunidad 1X (Local/Empate)',
  double_x2: 'Doble Oportunidad X2 (Empate/Visitante)',
  double_12: 'Doble Oportunidad 12 (Local/Visitante)',
  dnb_home: 'Empate No Válido: Local (DNB)',
  dnb_away: 'Empate No Válido: Visitante (DNB)',
  btts_yes: 'Ambos Anotan: Sí',
  btts_no: 'Ambos Anotan: No',
  '1x2_home': 'Ganador Local (1)',
  home_win: 'Ganador Local (1)',
  '1x2_draw': 'Empate (X)',
  draw: 'Empate (X)',
  '1x2_away': 'Ganador Visitante (2)',
  away_win: 'Ganador Visitante (2)',
}

function decimal(value: string, fraction: string): string {
  return formatDecimal(`${value}.${fraction}`, 1)
}

function titleCase(value: string): string {
  return value.replace(/(^|\s)\S/g, (character) => character.toUpperCase())
}

export function formatMarketName(rawMarket: string): string {
  const raw = rawMarket.trim()
  if (!raw) return ''

  const normalized = raw
    .toLowerCase()
    .replace(/[–—−]/g, '-')
    .replace(/\s+/g, '_')
  const exact = EXACT_NAMES[normalized]
  if (exact) return exact

  const spanishLine = normalized.match(/^(más|mas|menos)_de_(\d+)[_.](\d+)_goles$/)
  if (spanishLine) {
    return `${spanishLine[1] === 'menos' ? 'Menos de' : 'Más de'} ${decimal(spanishLine[2], spanishLine[3])} Goles`
  }

  const line = normalized.match(/^(?:o|over)_?(\d+)[_.](\d+)$/)
  if (line) return `Más de ${decimal(line[1], line[2])} Goles`

  const under = normalized.match(/^(?:u|under)_?(\d+)[_.](\d+)$/)
  if (under) return `Menos de ${decimal(under[1], under[2])} Goles`

  const corners = normalized.match(/^corners_(over|under)_(\d+)[_.](\d+)$/)
  if (corners) {
    return `${corners[1] === 'over' ? 'Más de' : 'Menos de'} ${decimal(corners[2], corners[3])} Córneres`
  }

  const cards = normalized.match(/^cards_(over|under)_(\d+)[_.](\d+)$/)
  if (cards) {
    return `${cards[1] === 'over' ? 'Más de' : 'Menos de'} ${decimal(cards[2], cards[3])} Tarjetas`
  }

  const shots = normalized.match(/^shots(?:_ot)?_(over|under)_(\d+)[_.](\d+)$/)
  if (shots) {
    return `${shots[1] === 'over' ? 'Más de' : 'Menos de'} ${decimal(shots[2], shots[3])} Remates al Arco`
  }

  // Covers future engine variants while keeping decimals and Spanish labels stable.
  let fallback = normalized.replace(/(\d+)[_ ](\d+)/g, '$1.$2').replace(/_/g, ' ')
  fallback = fallback
    .replace(/\bover\b/gi, 'Más de')
    .replace(/\bunder\b/gi, 'Menos de')
    .replace(/\bcorners?\b/gi, 'Córneres')
    .replace(/\bcards?\b/gi, 'Tarjetas')
    .replace(/\bshots?(?: ot)?\b/gi, 'Remates al Arco')
    .replace(/\bbtts yes\b/gi, 'Ambos Anotan: Sí')
    .replace(/\bbtts no\b/gi, 'Ambos Anotan: No')
    .replace(/\s+/g, ' ')
    .trim()

  return titleCase(fallback)
}
