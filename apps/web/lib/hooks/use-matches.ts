'use client'

import useSWR from 'swr'
import { fetchMatches } from '@/lib/api'
import type { Match } from '@/lib/betmind'

/**
 * Build a stable SWR key from the optional date filter.
 * Two components requesting the same date will share one request + cache.
 */
function matchesKey(dateFilter?: string): string {
  return dateFilter ? `/matches/?date=${dateFilter}` : '/matches/'
}

interface UseMatchesResult {
  matches: Match[]
  isLoading: boolean
  error: boolean
  revalidate: () => void
}

/**
 * useMatches — SWR-backed hook for the match list.
 *
 * Components requesting the same dateFilter share a single in-flight request
 * and the cached result for the dedupingInterval window (30s by default).
 */
export function useMatches(dateFilter?: string): UseMatchesResult {
  const {
    data: matches,
    isLoading,
    error: swrError,
    mutate,
  } = useSWR<Match[]>(
    matchesKey(dateFilter),
    () => fetchMatches(dateFilter).then((result) => {
      if (!result.ok) throw new Error(result.error.message)
      return result.data
    }),
    {
      revalidateOnFocus: false,
      keepPreviousData: true,
    },
  )

  return {
    matches: matches ?? [],
    isLoading,
    error: !!swrError,
    revalidate: () => mutate(),
  }
}
