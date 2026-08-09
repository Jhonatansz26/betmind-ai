'use client'

import * as React from 'react'

import { getBankroll, type Bankroll } from '@/lib/bankroll'

export function useBankroll(enabled: boolean) {
  const [bankroll, setBankroll] = React.useState<Bankroll | null>(null)
  const [loading, setLoading] = React.useState(enabled)
  const [error, setError] = React.useState<string | null>(null)

  const reload = React.useCallback(async () => {
    if (!enabled) {
      setBankroll(null)
      setLoading(false)
      return null
    }
    setLoading(true)
    setError(null)
    try {
      const next = await getBankroll()
      setBankroll(next)
      return next
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : 'No se pudo cargar tu bankroll.'
      setError(message)
      return null
    } finally {
      setLoading(false)
    }
  }, [enabled])

  React.useEffect(() => {
    void reload()
  }, [reload])

  return { bankroll, setBankroll, loading, error, reload }
}
