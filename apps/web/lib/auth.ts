'use client'

/**
 * lib/auth.ts
 * ~~~~~~~~~~~
 * BetMind auth primitives — JWT propio, sin Supabase.
 *
 * Token storage format:  localStorage["betmind_access_token"] = '{ "access_token": "<jwt>" }'
 * This is the exact format that lib/api.ts > getStoredAuthToken() already reads
 * (line ~21), so no changes to the API client are required.
 *
 * Events:
 *   "betmind:auth-changed" — dispatched on login, register, logout, and
 *   successful password reset so reactive listeners (TopNav, etc.)
 *   update without a full page reload.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
export const TOKEN_KEY = 'betmind_access_token'

/* ── Types ───────────────────────────────────────────────────────────── */

export interface AuthTokenPayload {
  access_token: string
  token_type: string
}

export interface UserMe {
  id: number
  email: string
  full_name?: string | null
  is_active: boolean
  is_pro: boolean
  pro_expires_at?: string | null
}

/* ── Token storage ───────────────────────────────────────────────────── */

function storeToken(payload: AuthTokenPayload): void {
  setCachedIsPro(null)
  localStorage.setItem(TOKEN_KEY, JSON.stringify({ access_token: payload.access_token }))
  window.dispatchEvent(new Event('betmind:auth-changed'))
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  setCachedIsPro(null)
  window.dispatchEvent(new Event('betmind:auth-changed'))
}

export function hasSession(): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem(TOKEN_KEY) !== null
}

/* ── Error parsing ───────────────────────────────────────────────────── */

async function parseApiError(res: Response): Promise<Error> {
  try {
    const body = (await res.json()) as { detail?: string; message?: string }
    return new Error(body.detail ?? body.message ?? 'Ocurrió un error inesperado.')
  } catch {
    return new Error('Ocurrió un error inesperado.')
  }
}

/* ── Auth endpoints ──────────────────────────────────────────────────── */

export async function register(
  email: string,
  password: string,
  ageConfirmed: boolean,
  fullName?: string,
): Promise<AuthTokenPayload> {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      full_name: fullName ?? undefined,
      age_confirmed: ageConfirmed,
    }),
  })
  if (!res.ok) throw await parseApiError(res)
  const data = (await res.json()) as AuthTokenPayload
  storeToken(data)
  return data
}

export async function login(email: string, password: string): Promise<AuthTokenPayload> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw await parseApiError(res)
  const data = (await res.json()) as AuthTokenPayload
  storeToken(data)
  return data
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  // This endpoint always returns 200 by design — don't treat non-200 as "email not found"
  if (!res.ok) throw await parseApiError(res)
  return res.json() as Promise<{ message: string }>
}

export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  })
  if (!res.ok) throw await parseApiError(res)
  const data = (await res.json()) as { message: string }
  // Dispatch auth-changed so any cached user state clears correctly
  window.dispatchEvent(new Event('betmind:auth-changed'))
  return data
}

export async function fetchMe(): Promise<UserMe | null> {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem(TOKEN_KEY)
  if (!raw) return null
  let access_token: string
  try {
    access_token = (JSON.parse(raw) as { access_token: string }).access_token
  } catch {
    return null
  }
  const res = await fetch(`${API_BASE}/api/v1/users/me`, {
    headers: { Authorization: `Bearer ${access_token}` },
  })
  if (res.status === 401) {
    clearToken() // expired or invalid — clear session immediately
    return null
  }
  if (!res.ok) throw await parseApiError(res)
  const data = await res.json() as UserMe
  setCachedIsPro(data.is_pro)
  return data
}

/* ── Pro Status Cache ────────────────────────────────────────────────── */

let cachedIsPro: boolean | null = null

export function getCachedIsPro(): boolean | null {
  return cachedIsPro
}

export function setCachedIsPro(value: boolean | null): void {
  cachedIsPro = value
}
