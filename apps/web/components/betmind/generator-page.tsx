'use client'

import * as React from 'react'

import { useAuthSession } from '@/lib/hooks/use-auth-session'
import { useMatches } from '@/lib/hooks/use-matches'
import { useLeagues } from '@/lib/hooks/use-leagues'

import { AppShell } from './app-shell'
import { RouteError, RouteSkeleton } from './route-states'
import { StatDisclaimer } from './stat-disclaimer'
import { TicketGenerator } from './ticket-generator'
import { UnlockGate, UnlocksBanner } from './access-gate'
import { useProStatus } from './use-pro-status'

export function GeneratorPage() {
  // TODO(backend-pagos): reemplazar por chequeo real de suscripción.
  const isPro = useProStatus()
  const { isAuthenticated, isLoading: authLoading } = useAuthSession()

  // SWR-backed — shared cache with MatchesPage and HomePage for 'today'.
  const { matches, isLoading: matchesLoading, error: matchesError, revalidate } = useMatches('today')
  const { leagues } = useLeagues()

  const loading = matchesLoading
  const error = matchesError

  // Cuota diaria restante del plan gratuito (la manda el backend).
  const unlocksRemaining = React.useMemo(() => {
    for (const match of matches) {
      if (match.unlocksRemaining != null) return match.unlocksRemaining
    }
    return null
  }, [matches])

  return (
    <AppShell activeLeagueCount={leagues.filter((league) => league.active_matches > 0).length}>
      <div className="flex flex-col gap-5">
        <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Constructor</p><h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">Generador de boletos</h1><p className="mt-1 text-sm text-subtle">Configura tu selección y deja que el modelo encuentre las mejores combinaciones.</p></div>

        {authLoading ? <RouteSkeleton rows={2} /> : !isAuthenticated ? (
          <>
            <UnlockGate
              variant="register"
              title="Registrate gratis para generar tus boletos"
              body="Los pronósticos se generan con el análisis completo del modelo, por eso requieren una cuenta. Registrate sin costo y desbloqueá hasta 3 pronósticos por día."
            />
            <StatDisclaimer />
          </>
        ) : loading ? <RouteSkeleton rows={2} /> : error ? <RouteError label="los partidos del generador" onRetry={revalidate} /> : <>
          {unlocksRemaining != null && <UnlocksBanner remaining={unlocksRemaining} />}
          <TicketGenerator leagues={leagues} isPro={isPro} dateFilter="today" />
          <StatDisclaimer />
        </>}
      </div>
    </AppShell>
  )
}
