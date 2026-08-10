'use client'

import useSWR from 'swr'
import { fetchLeagues, type LeagueData } from '@/lib/api'

/**
 * Build a stable SWR key from the optional date filter.
 * MatchesPage and GeneratorPage requesting the same date share one request.
 */
function leaguesKey(targetDate?: string): string {
  return targetDate ? `/leagues/?date=${targetDate}` : '/leagues/'
}

interface UseLeaguesResult {
  leagues: LeagueData[]
  isLoading: boolean
  error: boolean
}

/**
 * useLeagues — SWR-backed hook for the league list.
 *
 * The key is built from the optional targetDate so two components with the
 * same date share a single cached fetch.
 */
export function useLeagues(targetDate?: string): UseLeaguesResult {
  const {
    data: leagues,
    isLoading,
    error: swrError,
  } = useSWR<LeagueData[]>(
    leaguesKey(targetDate),
    () => fetchLeagues(targetDate).then((result) => {
      if (!result.ok) throw new Error(result.error.message)
      return result.data
    }),
    {
      revalidateOnFocus: false,
      keepPreviousData: true,
    },
  )

  return {
    leagues: leagues ?? [],
    isLoading,
    error: !!swrError,
  }
}
