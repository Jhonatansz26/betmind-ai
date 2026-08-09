import { API_BASE, apiFetch, type ApiResult } from './api'

export type RiskProfile = 'conservador' | 'moderado' | 'agresivo'

export interface BankrollMovement {
  id: string
  type: 'ticket_won' | 'ticket_lost' | 'ticket_void' | 'manual_adjustment'
  amount: number
  ticket_id?: string
  reason?: string
  created_at: string
}

export interface Bankroll {
  id: string
  current_capital: number
  risk_profile: RiskProfile
  created_at: string
  movements: BankrollMovement[]
}

interface BackendMovement {
  id: number
  type: BankrollMovement['type']
  amount: number
  ticket_id?: number | null
  reason?: string | null
  created_at: string
}

interface BackendBankroll {
  id: number
  current_capital: number
  risk_profile: RiskProfile
  created_at: string
  movements: BackendMovement[]
}

function mapMovement(movement: BackendMovement): BankrollMovement {
  return {
    id: String(movement.id),
    type: movement.type,
    amount: movement.amount,
    ...(movement.ticket_id != null ? { ticket_id: String(movement.ticket_id) } : {}),
    ...(movement.reason != null ? { reason: movement.reason } : {}),
    created_at: movement.created_at,
  }
}

function mapBankroll(bankroll: BackendBankroll): Bankroll {
  return {
    id: String(bankroll.id),
    current_capital: bankroll.current_capital,
    risk_profile: bankroll.risk_profile,
    created_at: bankroll.created_at,
    movements: bankroll.movements.map(mapMovement),
  }
}

function unwrap<T>(result: ApiResult<T>): T {
  if (result.ok) return result.data
  throw new Error(result.error.message)
}

export async function setupBankroll(
  initialCapital: number,
  riskProfile: RiskProfile,
): Promise<Bankroll> {
  const result = await apiFetch<BackendBankroll>(`${API_BASE}/api/v1/bankroll/setup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ initial_capital: initialCapital, risk_profile: riskProfile }),
  })
  if (!result.ok && result.error.code === 'HTTP_409') {
    throw new Error('Ya tenés un bankroll configurado. Podés modificarlo desde esta pantalla.')
  }
  return mapBankroll(unwrap(result))
}

export async function getBankroll(): Promise<Bankroll | null> {
  const result = await apiFetch<BackendBankroll>(`${API_BASE}/api/v1/bankroll`)
  if (!result.ok && result.error.code === 'HTTP_404') return null
  return mapBankroll(unwrap(result))
}

export async function updateRiskProfile(riskProfile: RiskProfile): Promise<Bankroll> {
  const result = await apiFetch<BackendBankroll>(`${API_BASE}/api/v1/bankroll`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ risk_profile: riskProfile }),
  })
  return mapBankroll(unwrap(result))
}

/** The real endpoint returns the complete updated bankroll, not only a movement. */
export async function adjustBankroll(amount: number, reason: string): Promise<Bankroll> {
  const result = await apiFetch<BackendBankroll>(`${API_BASE}/api/v1/bankroll/adjust`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount, reason }),
  })
  return mapBankroll(unwrap(result))
}
