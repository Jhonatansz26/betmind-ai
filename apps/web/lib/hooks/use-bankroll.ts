'use client'

import useSWR, { mutate as globalMutate } from 'swr'
import { getBankroll, type Bankroll } from '@/lib/bankroll'

/** Build a stable SWR key — null disables fetching when isPro is false. */
function bankrollKey(isPro: boolean): string | null {
  return isPro ? '/bankroll' : null
}

/**
 * useBankroll — SWR-backed hook for the current user's bankroll.
 *
 * All components that call useBankroll(true) share a single request
 * and a single cache entry — this replaces the per-component fetch pattern
 * that was causing N requests for N TicketCard instances.
 *
 * Interface matches the original use-bankroll.ts in components/betmind/:
 *   { bankroll, setBankroll, loading, error, reload }
 */
export function useBankroll(isPro: boolean) {
  const {
    data: bankroll = null,
    isLoading: loading,
    error: swrError,
    mutate,
  } = useSWR<Bankroll | null>(
    bankrollKey(isPro),
    () => getBankroll(),
    {
      revalidateOnFocus: false,
      keepPreviousData: true,
    },
  )

  const error: string | null = swrError instanceof Error
    ? swrError.message
    : swrError != null
      ? 'No se pudo cargar tu bankroll.'
      : null

  return {
    bankroll,
    /** Optimistic local update — use after API mutations. */
    setBankroll: (next: Bankroll | null) => mutate(next ?? undefined, { revalidate: false }),
    loading,
    error,
    reload: () => mutate(),
  }
}

/**
 * Invalidate the bankroll cache — call after setup, adjust, or
 * subscription changes so every consumer updates automatically.
 */
export function invalidateBankroll() {
  return globalMutate('/bankroll')
}
