'use client'

import { API_BASE, apiFetch, type ApiResult } from './api'

export type SubscriptionPlan = 'mensual' | 'anual'
export type SubscriptionStatus = 'trial' | 'pending_payment' | 'active' | 'past_due' | 'cancelled' | 'refund_requested'

export interface LastSubscriptionTransaction {
  id: string
  status: string
  status_message?: string | null
  processor_response_code?: string | null
}

export interface Subscription {
  id: number
  plan: SubscriptionPlan
  status: SubscriptionStatus
  created_at?: string | null
  current_period_end: string
  trial_ends_at?: string | null
  recurrence_enabled?: boolean | null
  last_transaction?: LastSubscriptionTransaction | null
  refund_eligible: boolean
}

export interface ActivationResponse extends Subscription {
  transaction_id: string
  transaction_status: string
}

export function refreshAuthSession() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('betmind:auth-changed'))
  }
}

export async function startSubscriptionTrial(): Promise<ApiResult<Subscription>> {
  return apiFetch<Subscription>(`${API_BASE}/api/v1/subscriptions/trial`, { method: 'POST' })
}

export async function fetchSubscription(): Promise<ApiResult<Subscription>> {
  return apiFetch<Subscription>(`${API_BASE}/api/v1/subscriptions/me`)
}

export async function activateSubscription(
  cardToken: string,
  plan: SubscriptionPlan,
  acceptanceToken: string,
  acceptPersonalAuth: string,
): Promise<ApiResult<ActivationResponse>> {
  return apiFetch<ActivationResponse>(`${API_BASE}/api/v1/subscriptions/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      card_token: cardToken,
      plan,
      acceptance_token: acceptanceToken,
      accept_personal_auth: acceptPersonalAuth,
    }),
  })
}

export async function cancelSubscription(): Promise<ApiResult<Subscription>> {
  return apiFetch<Subscription>(`${API_BASE}/api/v1/subscriptions/cancel`, { method: 'POST' })
}

export async function requestRefund(): Promise<ApiResult<Subscription>> {
  return apiFetch<Subscription>(`${API_BASE}/api/v1/subscriptions/refund`, { method: 'POST' })
}
