'use client'

import * as React from 'react'

import { fetchLeagues, fetchMatches, type LeagueData } from '@/lib/api'
import { announceProLimit } from '@/lib/subscription'

import { AppShell } from './app-shell'
import { RouteError, RouteSkeleton } from './route-states'
import { StatDisclaimer } from './stat-disclaimer'
import { TicketGenerator } from './ticket-generator'
import { useProStatus } from './use-pro-status'

const DAILY_GENERATIONS_KEY = 'betmind_daily_generations'

function todayKey() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(new Date())
}

function readDailyGenerations() {
  if (typeof window === 'undefined') return { date: todayKey(), count: 0 }
  try {
    const parsed = JSON.parse(window.localStorage.getItem(DAILY_GENERATIONS_KEY) ?? '') as { date?: string; count?: number }
    return parsed.date === todayKey() && typeof parsed.count === 'number' ? { date: parsed.date, count: parsed.count } : { date: todayKey(), count: 0 }
  } catch {
    return { date: todayKey(), count: 0 }
  }
}

export function GeneratorPage() {
  // TODO(backend-pagos): reemplazar por chequeo real de suscripción.
  const isPro = useProStatus()
  const [leagues, setLeagues] = React.useState<LeagueData[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(false)
  const [retryKey, setRetryKey] = React.useState(0)
  const [dailyGenerations, setDailyGenerations] = React.useState(0)

  React.useEffect(() => {
    setDailyGenerations(readDailyGenerations().count)
  }, [])

  const beforeGenerate = React.useCallback(() => {
    if (isPro) return true
    const current = readDailyGenerations()
    if (current.count >= 2) {
      announceProLimit('generations')
      return false
    }
    const next = { date: current.date, count: current.count + 1 }
    window.localStorage.setItem(DAILY_GENERATIONS_KEY, JSON.stringify(next))
    setDailyGenerations(next.count)
    return true
  }, [isPro])

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(false)
      const [matchesResult, leaguesResult] = await Promise.all([fetchMatches('today'), fetchLeagues()])
      if (cancelled) return
      if (!matchesResult.ok) {
        setLeagues(leaguesResult.ok ? leaguesResult.data : [])
        setError(true)
      } else {
        setLeagues(leaguesResult.ok ? leaguesResult.data : [])
      }
      setLoading(false)
    }
    void load()
    return () => { cancelled = true }
  }, [retryKey])

  return (
    <AppShell activeLeagueCount={leagues.filter((league) => league.active_matches > 0).length}>
      <div className="flex flex-col gap-5">
        <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Constructor</p><h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">Generador de boletos</h1><p className="mt-1 text-sm text-subtle">Configura tu selección y deja que el modelo encuentre las mejores combinaciones.</p></div>
        {!isPro && <p className="text-xs text-subtle">Generaciones gratuitas hoy: {dailyGenerations}/2 · <a href="/planes" className="font-semibold text-brand hover:underline">Desbloquear PRO</a></p>}
        {loading ? <RouteSkeleton rows={2} /> : error ? <RouteError label="los partidos del generador" onRetry={() => setRetryKey((key) => key + 1)} /> : <>
          <TicketGenerator leagues={leagues} isPro={isPro} onBeforeGenerate={beforeGenerate} dateFilter="today" />
          <StatDisclaimer />
        </>}
      </div>
    </AppShell>
  )
}
