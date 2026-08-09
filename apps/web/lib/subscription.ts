/**
 * lib/subscription.ts
 * ~~~~~~~~~~~~~~~~~~~
 * PRO-status helpers.
 *
 * When a user is authenticated the real `is_pro` flag from `GET /api/v1/users/me`
 * is the source of truth (via `useIsPro()` hook). The legacy `betmind_dev_is_pro`
 * localStorage flag is kept as a **dev-only fallback** for testing gates without
 * needing to log in. It is ignored whenever there is an active session.
 *
 * TODO(backend-pagos): `is_pro` is now connected to /users/me.
 * What remains pending is the real payment integration (Wompi) so that
 * is_pro is updated automatically after a successful charge — until then
 * it must be set manually in the database by the backend team.
 */

import * as React from 'react'
import { useAuthSession } from '@/lib/hooks/use-auth-session'
import { hasSession, getCachedIsPro } from '@/lib/auth'

const DEV_FLAG_KEY = 'betmind_dev_is_pro'
export const PRO_STATUS_CHANGED_EVENT = 'betmind:pro-status-changed'
export const PRO_LIMIT_REACHED_EVENT = 'betmind:pro-limit-reached'

/**
 * Synchronous check — reads the dev-flag from localStorage.
 * Used in non-reactive contexts (e.g. addToTracking gate).
 * NOTE: when there is an active session, prefer `useIsPro()` which
 * reflects the real `is_pro` field from the backend.
 */
export function isProUser(): boolean {
  if (typeof window === 'undefined') return false
  // When there IS a session, use the synchronously cached is_pro value.
  // If fetchMe() hasn't resolved yet (cached === null), fallback to false.
  if (hasSession()) {
    return getCachedIsPro() ?? false
  }
  // Dev-only fallback — only applies when there is no active session
  return window.localStorage.getItem(DEV_FLAG_KEY) === 'true'
}

/**
 * Reactive hook — returns the real `is_pro` when authenticated,
 * or the dev localStorage flag when there is no session.
 * Use this in all UI components instead of `isProUser()`.
 */
export function useIsPro(): boolean {
  const { user, isLoading } = useAuthSession()
  const [devFlag, setDevFlag] = React.useState(false)

  React.useEffect(() => {
    if (!hasSession()) {
      setDevFlag(window.localStorage.getItem(DEV_FLAG_KEY) === 'true')
    }
    const sync = () => {
      if (!hasSession()) setDevFlag(window.localStorage.getItem(DEV_FLAG_KEY) === 'true')
    }
    window.addEventListener(PRO_STATUS_CHANGED_EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(PRO_STATUS_CHANGED_EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  if (isLoading) return false       // while loading, assume free
  if (user) return user.is_pro      // real backend value when authenticated
  return devFlag                     // dev-only fallback without session
}

// Only for manual testing in development — not exposed in production UI
export function setDevProFlag(value: boolean) {
  window.localStorage.setItem(DEV_FLAG_KEY, String(value))
  window.dispatchEvent(new Event(PRO_STATUS_CHANGED_EVENT))
}

export function announceProLimit(kind: 'generations' | 'saved') {
  window.dispatchEvent(new CustomEvent(PRO_LIMIT_REACHED_EVENT, { detail: { kind } }))
}
