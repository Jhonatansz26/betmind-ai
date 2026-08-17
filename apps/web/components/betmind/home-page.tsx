'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'

import type { Ticket } from '@/lib/betmind'
import { fetchTickets } from '@/lib/api'
import { useAuthSession } from '@/lib/hooks/use-auth-session'
import { useMatches } from '@/lib/hooks/use-matches'
import { useProStatus } from './use-pro-status'

import { AppShell } from './app-shell'
import { HomeView } from './home'

function todayLabel() {
  return new Intl.DateTimeFormat('es-CO', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', timeZone: 'America/Bogota' }).format(new Date())
}

function greeting() {
  const hour = new Date().getHours()
  if (hour >= 19) return 'Buenas noches'
  if (hour >= 12) return 'Buenas tardes'
  return 'Buenos días'
}

export function HomePage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading } = useAuthSession()
  const isPro = useProStatus()
  const [tickets, setTickets] = React.useState<Ticket[]>([])
  const [ticketsLoading, setTicketsLoading] = React.useState(true)
  const [ticketsError, setTicketsError] = React.useState(false)
  /** 403 del backend (acceso sin sesión) → CTA de registro en vez de error. */
  const [ticketsAccessError, setTicketsAccessError] = React.useState(false)
  /** Free registrado: NO se auto-genera (la cuota se gasta al elegir partidos). */
  const [ticketsPick, setTicketsPick] = React.useState(false)
  const [ticketRetryKey, setTicketRetryKey] = React.useState(0)
  const [ticketCount, setTicketCount] = React.useState<number | null>(null)

  // useMatches shares the cache with MatchesPage and GeneratorPage —
  // if any of them already fetched today's matches, no new request is made.
  const { matches, isLoading: matchesLoading, error: matchesError, revalidate: retryMatches } = useMatches('today')

  React.useEffect(() => {
    let cancelled = false

    // Anónimos y free NO generan boletos automáticamente: la cuota de 3
    // desbloqueos se gasta solo cuando el usuario elige un partido.
    if (authLoading) return
    if (!isAuthenticated) {
      setTickets([])
      setTicketCount(null)
      setTicketsAccessError(true)
      setTicketsPick(false)
      setTicketsLoading(false)
      return
    }
    if (!isPro) {
      setTickets([])
      setTicketCount(null)
      setTicketsAccessError(false)
      setTicketsPick(true)
      setTicketsLoading(false)
      return
    }

    async function load() {
      setTicketsLoading(true)
      setTicketsError(false)
      setTicketsAccessError(false)
      setTicketsPick(false)
      const result = await fetchTickets(['EDGE', 'VALUE', 'BOLD'], undefined, 'today')
      if (cancelled) return
      if (result.ok) {
        setTickets(result.data.tickets)
        setTicketCount(result.data.totalEvOpportunities)
      } else {
        setTickets([])
        setTicketCount(null)
        if (result.error.code === 'HTTP_403') setTicketsAccessError(true)
        else setTicketsError(true)
      }
      setTicketsLoading(false)
    }
    void load()
    return () => { cancelled = true }
  }, [authLoading, isAuthenticated, isPro, ticketRetryKey])

  return (
    <AppShell>
      <HomeView
        greeting={greeting()}
        dateLabel={todayLabel()}
        tickets={tickets}
        ticketsLoading={ticketsLoading}
        ticketsError={ticketsError}
        ticketsAccessError={ticketsAccessError}
        ticketsPick={ticketsPick}
        unlocksRemaining={matches.length > 0 ? (matches[0].unlocksRemaining ?? null) : null}
        ticketCount={ticketCount}
        onRetryTickets={() => setTicketRetryKey((key) => key + 1)}
        matches={matches}
        matchesLoading={matchesLoading}
        matchesError={matchesError}
        onRetryMatches={retryMatches}
        onOpenTickets={() => router.push('/senales')}
        onOpenGenerator={() => router.push('/generador')}
        onOpenMatches={() => router.push('/partidos')}
      />
    </AppShell>
  )
}
