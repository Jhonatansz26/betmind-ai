'use client'

/**
 * components/betmind/use-bankroll.ts
 *
 * Re-exports the SWR-backed useBankroll from lib/hooks for backward
 * compatibility — all existing consumers continue to work without changes.
 */
export { useBankroll, invalidateBankroll } from '@/lib/hooks/use-bankroll'
