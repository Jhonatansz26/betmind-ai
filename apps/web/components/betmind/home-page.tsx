'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'

import type { Match, Ticket } from '@/lib/betmind'
import { fetchMatches, fetchTickets } from '@/lib/api'

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
  const [tickets, setTickets] = React.useState<Ticket[]>([])
  const [matches, setMatches] = React.useState<Match[]>([])
  const [ticketsLoading, setTicketsLoading] = React.useState(true)
  const [matchesLoading, setMatchesLoading] = React.useState(true)
  const [ticketsError, setTicketsError] = React.useState(false)
  const [matchesError, setMatchesError] = React.useState(false)
  const [ticketRetryKey, setTicketRetryKey] = React.useState(0)
  const [matchesRetryKey, setMatchesRetryKey] = React.useState(0)
  const [ticketCount, setTicketCount] = React.useState<number | null>(null)

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      setTicketsLoading(true)
      setTicketsError(false)
      const result = await fetchTickets(['EDGE', 'VALUE', 'BOLD'], undefined, 'today')
      if (cancelled) return
      if (result.ok) {
        setTickets(result.data.tickets)
        setTicketCount(result.data.totalEvOpportunities)
      } else {
        setTickets([])
        setTicketCount(null)
        setTicketsError(true)
      }
      setTicketsLoading(false)
    }
    void load()
    return () => { cancelled = true }
  }, [ticketRetryKey])

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      setMatchesLoading(true)
      setMatchesError(false)
      const result = await fetchMatches('today')
      if (cancelled) return
      if (result.ok) setMatches(result.data)
      else {
        setMatches([])
        setMatchesError(true)
      }
      setMatchesLoading(false)
    }
    void load()
    return () => { cancelled = true }
  }, [matchesRetryKey])

  return (
    <AppShell>
      <HomeView
        greeting={greeting()}
        dateLabel={todayLabel()}
        tickets={tickets}
        ticketsLoading={ticketsLoading}
        ticketsError={ticketsError}
        ticketCount={ticketCount}
        onRetryTickets={() => setTicketRetryKey((key) => key + 1)}
        matches={matches}
        matchesLoading={matchesLoading}
        matchesError={matchesError}
        onRetryMatches={() => setMatchesRetryKey((key) => key + 1)}
        onOpenTickets={() => router.push('/senales')}
        onOpenGenerator={() => router.push('/generador')}
        onOpenMatches={() => router.push('/partidos')}
      />
    </AppShell>
  )
}
