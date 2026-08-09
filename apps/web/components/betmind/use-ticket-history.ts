'use client'

import * as React from 'react'

import { fetchTicketHistory } from '@/lib/api'
import { claimPendingTickets, loadTrackedTickets, mapSavedTicket, type TrackedTicket } from '@/lib/tracking'

export function useTicketHistory(isAuthenticated: boolean, authLoading: boolean) {
  const [entries, setEntries] = React.useState<TrackedTicket[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [reloadKey, setReloadKey] = React.useState(0)

  React.useEffect(() => {
    if (authLoading) return
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      if (isAuthenticated) {
        try {
          await claimPendingTickets()
          const result = await fetchTicketHistory()
          if (!result.ok) throw new Error(result.error.message)
          if (!cancelled) setEntries(result.data.map(mapSavedTicket))
        } catch (loadError) {
          if (!cancelled) {
            setEntries([])
            setError(loadError instanceof Error ? loadError.message : 'No se pudo cargar el historial.')
          }
        }
      } else if (!cancelled) {
        setEntries(loadTrackedTickets())
      }
      if (!cancelled) setLoading(false)
    }

    void load()
    return () => { cancelled = true }
  }, [authLoading, isAuthenticated, reloadKey])

  React.useEffect(() => {
    if (authLoading) return
    const sync = () => setReloadKey((key) => key + 1)
    window.addEventListener('storage', sync)
    window.addEventListener('betmind:auth-changed', sync)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener('betmind:auth-changed', sync)
    }
  }, [authLoading])

  return {
    entries,
    setEntries,
    loading: authLoading || loading,
    error,
    reload: () => setReloadKey((key) => key + 1),
  }
}
