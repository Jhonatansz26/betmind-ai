'use client'

/**
 * components/betmind/use-ticket-history.ts
 *
 * Re-exports the SWR-backed useTicketHistory from lib/hooks for backward
 * compatibility — all existing consumers continue to work without changes.
 */
export { useTicketHistory, invalidateTicketHistory } from '@/lib/hooks/use-ticket-history'
