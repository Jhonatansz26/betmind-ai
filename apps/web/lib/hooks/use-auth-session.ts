'use client'

import useSWR, { mutate as globalMutate } from 'swr'
import { useEffect } from 'react'
import { fetchMe, hasSession, type UserMe } from '@/lib/auth'
import { invalidateBankroll } from '@/lib/hooks/use-bankroll'

/** Stable SWR key for the current user session. */
export const AUTH_SESSION_KEY = '/users/me'

async function sessionFetcher(): Promise<UserMe | null> {
  if (!hasSession()) return null
  return fetchMe()
}

/**
 * useAuthSession — backed by SWR so all components that call this hook
 * share a single request and a single cached result.
 *
 * The original interface is preserved:
 *   { user, isLoading, isAuthenticated, refresh }
 *
 * The hook registers a window listener for the "betmind:auth-changed" event
 * and revalidates the SWR cache when it fires, so login/logout/register
 * propagate to every consumer automatically.
 */
export function useAuthSession() {
  const { data: user = null, isLoading, mutate } = useSWR<UserMe | null>(
    AUTH_SESSION_KEY,
    sessionFetcher,
    {
      revalidateOnFocus: false,
      keepPreviousData: true,
    },
  )

  // Revalidate on auth events (login, register, logout, subscription change).
  useEffect(() => {
    function handleAuthChanged() {
      void mutate()
      void invalidateBankroll()
    }
    window.addEventListener('betmind:auth-changed', handleAuthChanged)
    return () => window.removeEventListener('betmind:auth-changed', handleAuthChanged)
  }, [mutate])

  return {
    user,
    isLoading,
    isAuthenticated: !!user,
    /** Force a re-fetch — useful after login / logout. */
    refresh: () => mutate(),
  }
}

/**
 * Invalidate the session cache from outside a React component — call after
 * login, register, logout, or subscription changes.
 */
export function invalidateSession() {
  return globalMutate(AUTH_SESSION_KEY)
}
