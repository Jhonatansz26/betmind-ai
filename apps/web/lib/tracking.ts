import { claimAnonymousTickets, type SavedTicketRecord, type SavedTicketStatus } from './api'
import type { Mode } from './betmind'

export type TrackStatus = SavedTicketStatus

export interface TrackedTicket {
  id: string
  mode: Mode
  combinedOdds: number
  evAverage: number
  confidence: number
  legsCount: number
  trackedAt: string
  status: TrackStatus
  stakeAmount?: number | null
  remote?: boolean
}

export const TRACKED_TICKETS_STORAGE_KEY = 'betmind_tracked_tickets'

export function mapSavedTicket(saved: SavedTicketRecord): TrackedTicket {
  return {
    id: String(saved.id),
    mode: saved.ticket_data.mode,
    combinedOdds: saved.total_odds,
    evAverage: saved.total_ev,
    confidence: saved.ticket_data.confidence,
    legsCount: saved.ticket_data.legs.length,
    trackedAt: saved.created_at,
    status: saved.status,
    stakeAmount: saved.stake_amount,
    remote: true,
  }
}

export async function claimPendingTickets(): Promise<number> {
  const pending = loadTrackedTickets().filter((ticket) => ticket.remote && /^\d+$/.test(ticket.id))
  const ticketIds = pending.map((ticket) => Number(ticket.id))
  if (!ticketIds.length) return 0

  const result = await claimAnonymousTickets(ticketIds)
  if (!result.ok || result.data.claimed_count <= 0) return 0

  const claimedIds = new Set((result.data.claimed_ticket_ids ?? []).map(String))
  saveTrackedTickets(loadTrackedTickets().filter((ticket) => !claimedIds.has(ticket.id)))
  return result.data.claimed_count
}

export function loadTrackedTickets(): TrackedTicket[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(TRACKED_TICKETS_STORAGE_KEY)
    const parsed = raw ? (JSON.parse(raw) as TrackedTicket[]) : []
    return parsed.map((ticket) => ({ ...ticket, evAverage: ticket.evAverage ?? 0 }))
  } catch {
    return []
  }
}

export function saveTrackedTickets(tickets: TrackedTicket[]) {
  try {
    window.localStorage.setItem(TRACKED_TICKETS_STORAGE_KEY, JSON.stringify(tickets))
  } catch {
    // Storage may be unavailable or full; the caller can continue with in-memory state.
  }
}

export interface TrackingSummary {
  total: number
  active: number
  won: number
  lost: number
  roiApprox: number | null
  roiTicketCount: number
  streakStatus: 'WON' | 'LOST' | null
  streakCount: number
}

export function summarizeTrackedTickets(entries: TrackedTicket[]): TrackingSummary {
  const ordered = [...entries].sort((a, b) => new Date(b.trackedAt).getTime() - new Date(a.trackedAt).getTime())
  const firstEntry = ordered[0]
  const streakStatus = firstEntry?.status === 'WON' || firstEntry?.status === 'LOST' ? firstEntry.status : null
  const streakBreakIndex = streakStatus ? ordered.findIndex((entry) => entry.status !== streakStatus) : -1
  const streakCount = streakStatus ? (streakBreakIndex === -1 ? ordered.length : streakBreakIndex) : 0
  const bankrollEntries = entries.filter((entry) => entry.stakeAmount != null)
  const resolvedWithStake = bankrollEntries.filter((entry) => entry.status !== 'PENDING')
  const totalStake = resolvedWithStake.reduce((sum, entry) => sum + (entry.stakeAmount ?? 0), 0)
  const netResult = resolvedWithStake.reduce((sum, entry) => {
    const stake = entry.stakeAmount ?? 0
    if (entry.status === 'WON') return sum + stake * (entry.combinedOdds - 1)
    if (entry.status === 'LOST') return sum - stake
    return sum
  }, 0)

  return {
    total: entries.length,
    active: entries.filter((entry) => entry.status === 'PENDING').length,
    won: entries.filter((entry) => entry.status === 'WON').length,
    lost: entries.filter((entry) => entry.status === 'LOST').length,
    roiApprox: totalStake > 0 ? (netResult / totalStake) * 100 : null,
    roiTicketCount: resolvedWithStake.length,
    streakStatus,
    streakCount,
  }
}
