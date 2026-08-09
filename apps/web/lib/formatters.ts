const COT_TIME_ZONE = 'America/Bogota'

function finite(value: number): boolean {
  return Number.isFinite(value)
}

/** Cuota decimal, siempre con dos decimales para columnas tabulares. */
export function formatOdds(odds: number): string {
  return finite(odds) ? odds.toFixed(2) : '—'
}

/** EV expresado como porcentaje firmado; recibe una fracción decimal. */
export function formatEV(ev: number): string {
  if (!finite(ev)) return '—'
  return `${ev >= 0 ? '+' : ''}${(ev * 100).toFixed(1)}%`
}

/** Goles esperados con precisión fija para lectura cuantitativa. */
export function formatxG(xg: number): string {
  return finite(xg) ? xg.toFixed(2) : '—'
}

/** Porcentaje para probabilidades expresadas como fracción [0, 1]. */
export function formatPercent(value: number, digits = 1): string {
  return finite(value) ? `${(value * 100).toFixed(digits)}%` : '—'
}

/** Fecha/hora normalizada a la zona horaria oficial de BetMind (Colombia). */
export function formatCOTDate(dateStr: string): string {
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return 'Fecha no disponible'
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: COT_TIME_ZONE,
  }).format(date)
}

/** Decimal estable para nombres de mercados: 10.5, 3.5, etc. */
export function formatDecimal(value: number | string, digits = 1): string {
  const numeric = Number(value)
  return finite(numeric) ? numeric.toFixed(digits) : String(value)
}

const COP_FORMATTER = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

export function formatCOP(value: number): string {
  return finite(value) ? COP_FORMATTER.format(value) : '—'
}

export function formatCOPInput(value: number): string {
  return finite(value) ? Math.round(value).toLocaleString('es-CO') : ''
}

/** Parse the integer COP input used by the bankroll forms. */
export function parseCOPInput(value: string): number | null {
  const trimmed = value.trim()
  const digits = trimmed.replace(/\D/g, '')
  if (!digits) return null
  const amount = Number(digits)
  if (!Number.isFinite(amount)) return null
  return trimmed.includes('-') ? -amount : amount
}
