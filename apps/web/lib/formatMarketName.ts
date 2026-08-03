const EXACT_NAMES: Record<string, string> = {
  double_1x: 'Doble Oportunidad 1X (Local/Empate)',
  double_x2: 'Doble Oportunidad X2 (Empate/Visitante)',
  double_12: 'Doble Oportunidad 12 (Local/Visitante)',
  dnb_home: 'Empate No Válido: Local (DNB)',
  dnb_away: 'Empate No Válido: Visitante (DNB)',
  btts_yes: 'Ambos Anotan: Sí',
  btts_no: 'Ambos Anotan: No',
  '1x2_home': 'Gana Local',
  '1x2_draw': 'Empate',
  '1x2_away': 'Gana Visitante',
}

function prettifyLine(line: string, prefix: string) {
  const value = line.replace(/_/g, '.').replace(/\s+/g, '')
  return `${prefix} ${value} Goles`
}

export function formatMarketName(raw: string): string {
  const normalized = raw.trim().toLowerCase().replace(/\s+/g, '_')
  if (EXACT_NAMES[normalized]) return EXACT_NAMES[normalized]

  const over = normalized.match(/^(?:over|más_de|mas_de)_(\d+)[_.](\d+)$/)
  if (over) return prettifyLine(`${over[1]}_${over[2]}`, 'Más de')

  const under = normalized.match(/^(?:under|menos_de)_(\d+)[_.](\d+)$/)
  if (under) return prettifyLine(`${under[1]}_${under[2]}`, 'Menos de')

  const teamGoals = normalized.match(/^(home|away)_over_(\d+)_(\d+)$/)
  if (teamGoals) return `${teamGoals[1] === 'home' ? 'Local' : 'Visitante'} · Más de ${teamGoals[2]}.${teamGoals[3]} Goles`

  const corners = normalized.match(/^corners_(over|under)_(\d+)_(\d+)$/)
  if (corners) return `Córneres · ${corners[1] === 'over' ? 'Más de' : 'Menos de'} ${corners[2]}.${corners[3]}`

  const cards = normalized.match(/^cards_(over|under)_(\d+)_(\d+)$/)
  if (cards) return `Tarjetas · ${cards[1] === 'over' ? 'Más de' : 'Menos de'} ${cards[2]}.${cards[3]}`

  const shots = normalized.match(/^shots_ot_(over|under)_(\d+)_(\d+)$/)
  if (shots) return `Remates a puerta · ${shots[1] === 'over' ? 'Más de' : 'Menos de'} ${shots[2]}.${shots[3]}`

  const words = normalized
    .replace(/_/g, ' ')
    .replace(/\b(ot|ot)\b/g, 'a puerta')
    .trim()

  return words.replace(/(^|\s)\S/g, (character) => character.toUpperCase())
}
