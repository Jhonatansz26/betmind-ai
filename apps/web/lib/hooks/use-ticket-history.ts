'use client'

import useSWR, { mutate as globalMutate } from 'swr'
import { fetchTicketHistory } from '@/lib/api'
import { claimPendingTickets, loadTrackedTickets, mapSavedTicket, type TrackedTicket } from '@/lib/tracking'

/** Stable SWR key — only fetch when authenticated. */
function ticketHistoryKey(isAuthenticated: boolean, authLoading: boolean): string | null {
  if (authLoading) return null         // not ready yet
  return isAuthenticated ? '/tickets/history' : '/tickets/history/local'
}

const TICKET_HISTORY_REMOTE_KEY = '/tickets/history'
const TICKET_HISTORY_LOCAL_KEY = '/tickets/history/local'

async function remoteHistoryFetcher(): Promise<TrackedTicket[]> {
  await claimPendingTickets()
  const result = await fetchTicketHistory()
  if (!result.ok) throw new Error(result.error.message)
  return result.data.map(mapSavedTicket)
}

function localHistoryFetcher(): TrackedTicket[] {
  return loadTrackedTickets()
}

interface UseTicketHistoryResult {
  entries: TrackedTicket[]
  setEntries: (next: TrackedTicket[]) => void
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * useTicketHistory — SWR-backed hook for ticket history.
 *
 * HomeView and HistoryPage calling this hook with the same auth state share
 * one cached result instead of making two independent requests.
 *
 * The interface matches the original use-ticket-history.ts:
 *   { entries, setEntries, loading, error, reload }
 */
export function useTicketHistory(
  isAuthenticated: boolean,
  authLoading: boolean,
): UseTicketHistoryResult {
  const key = ticketHistoryKey(isAuthenticated, authLoading)
  const isRemote = isAuthenticated && !authLoading

  const {
    data: entries,
    isLoading,
    error: swrError,
    mutate,
  } = useSWR<TrackedTicket[]>(
    key,
    isRemote ? remoteHistoryFetcher : localHistoryFetcher,
    {
      revalidateOnFocus: false,
      keepPreviousData: true,
    },
  )

  return {
    entries: entries ?? [],
    setEntries: (next: TrackedTicket[]) => mutate(next, { revalidate: false }),
    loading: authLoading || isLoading,
    error: swrError instanceof Error ? swrError.message : swrError != null ? 'No se pudo cargar el historial.' : null,
    reload: () => mutate(),
  }
}

/**
 * Invalidate the ticket history cache — call after saving a ticket so
 * HomeView and HistoryPage both refresh automatically.
 */
export function invalidateTicketHistory() {
  return Promise.all([
    globalMutate(TICKET_HISTORY_REMOTE_KEY),
    globalMutate(TICKET_HISTORY_LOCAL_KEY),
  ])
}
