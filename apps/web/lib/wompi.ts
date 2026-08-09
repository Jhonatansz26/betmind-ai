'use client'

import { EncryptJWT, importSPKI, type JWTPayload } from 'jose'

import { API_BASE, apiFetch } from './api'

const WOMPI_BASE_URL = (process.env.NEXT_PUBLIC_WOMPI_BASE_URL ?? 'https://sandbox.wompi.co/v1').replace(/\/$/, '')
const WOMPI_PUBLIC_KEY = process.env.NEXT_PUBLIC_WOMPI_PUBLIC_KEY ?? ''

export interface WompiAcceptance {
  acceptance_token: string
  permalink: string
  type: string
}

export interface WompiMerchantAcceptance {
  presigned_acceptance: WompiAcceptance
  presigned_personal_data_auth: WompiAcceptance
}

export interface CardDetails {
  number: string
  exp_month: string
  exp_year: string
  cvc: string
  card_holder: string
}

export interface WompiCardToken {
  card_token: string
  acceptance_token: string
  accept_personal_auth: string
}

interface WompiResponse<T> {
  data?: T
  status?: string
  error?: { type?: string; reason?: string }
  message?: string
}

function requirePublicKey() {
  if (!WOMPI_PUBLIC_KEY) {
    throw new Error('La llave pública de Wompi no está configurada en el frontend.')
  }
  return WOMPI_PUBLIC_KEY
}

async function parseWompiResponse<T>(response: Response): Promise<WompiResponse<T>> {
  try {
    return await response.json() as WompiResponse<T>
  } catch {
    return {}
  }
}

function wompiError(body: WompiResponse<unknown>, fallback: string) {
  return body.error?.reason ?? body.message ?? fallback
}

export async function fetchWompiAcceptance(): Promise<WompiMerchantAcceptance> {
  const publicKey = requirePublicKey()
  const response = await fetch(`${WOMPI_BASE_URL}/merchants/${encodeURIComponent(publicKey)}`, {
    headers: { Authorization: `Bearer ${publicKey}` },
  })
  const body = await parseWompiResponse<WompiMerchantAcceptance>(response)
  if (!response.ok || !body.data?.presigned_acceptance || !body.data.presigned_personal_data_auth) {
    throw new Error(wompiError(body, 'Wompi no devolvió los contratos de aceptación.'))
  }
  return body.data
}

async function fetchTokenizationKey(): Promise<string> {
  const result = await apiFetch<{ public_key?: string }>(`${API_BASE}/api/v1/subscriptions/wompi-tokenization-key`)
  if (!result.ok || !result.data.public_key) {
    throw new Error(result.ok ? 'Wompi no devolvió la llave de tokenización.' : result.error.message)
  }
  return result.data.public_key
}

async function encryptCard(card: CardDetails, tokenizationKey: string): Promise<string> {
  const encryptionKey = await importSPKI(tokenizationKey, 'RSA-OAEP-256')
  return new EncryptJWT(card as unknown as JWTPayload)
    .setProtectedHeader({ alg: 'RSA-OAEP-256', enc: 'A256GCM' })
    .encrypt(encryptionKey)
}

export async function tokenizeCard(
  card: CardDetails,
  acceptance: WompiMerchantAcceptance,
): Promise<WompiCardToken> {
  const publicKey = requirePublicKey()
  const tokenizationKey = await fetchTokenizationKey()
  const payload = await encryptCard(card, tokenizationKey)
  const response = await fetch(`${WOMPI_BASE_URL}/tokens/cards`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${publicKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ payload }),
  })
  const body = await parseWompiResponse<{ id?: string }>(response)
  const cardToken = body.data?.id
  if (!response.ok || !cardToken) {
    throw new Error(wompiError(body, 'Wompi no pudo tokenizar esta tarjeta.'))
  }

  return {
    card_token: cardToken,
    acceptance_token: acceptance.presigned_acceptance.acceptance_token,
    accept_personal_auth: acceptance.presigned_personal_data_auth.acceptance_token,
  }
}
