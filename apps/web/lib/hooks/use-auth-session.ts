'use client'

import * as React from 'react'
import { fetchMe, hasSession, type UserMe } from '@/lib/auth'

export function useAuthSession() {
  const [user, setUser] = React.useState<UserMe | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)

  const refresh = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const me = hasSession() ? await fetchMe() : null
      setUser(me)
    } catch {
      // Network error during refresh — don't clear the session,
      // just leave the previous user state intact.
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void refresh()
    window.addEventListener('betmind:auth-changed', refresh)
    return () => window.removeEventListener('betmind:auth-changed', refresh)
  }, [refresh])

  return { user, isLoading, isAuthenticated: !!user, refresh }
}
