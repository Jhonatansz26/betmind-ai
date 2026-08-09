'use client'

import * as React from 'react'
import { toast } from 'sonner'
import { CopyIcon, Share2, StarIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { MODE_META, type Ticket } from '@/lib/betmind'
import { useBankroll } from './use-bankroll'
import { formatMarketName } from '@/lib/formatMarketName'
import { formatEV, formatOdds } from '@/lib/formatters'
import { shareOrDownloadTicket } from '@/lib/ticket-export'
import { cn } from '@/lib/utils'
import { TicketLeg } from './ticket-leg'
import { addToTracking } from './tracking-panel'
import { StatDisclaimer } from './stat-disclaimer'
import { StakeConfirmDialog } from './stake-confirm-dialog'
import { useProStatus } from './use-pro-status'

export function TicketCard({ ticket, onTrack }: { ticket: Ticket; onTrack?: (ticket: Ticket) => void }) {
  const meta = MODE_META[ticket.mode]
  const [currentTicket, setCurrentTicket] = React.useState(ticket)
  const isPro = useProStatus()
  const { bankroll, loading: bankrollLoading } = useBankroll(isPro)
  const [stakeDialogOpen, setStakeDialogOpen] = React.useState(false)

  function swapLeg(index: number) {
    const replacement = currentTicket.replacementCandidates?.find((candidate) => !currentTicket.legs.some((leg, legIndex) => legIndex !== index && leg.match === candidate.match))
    if (!replacement) return
    setCurrentTicket((current) => ({ ...current, legs: current.legs.map((leg, legIndex) => legIndex === index ? replacement : leg), replacementCandidates: current.replacementCandidates?.filter((candidate) => candidate !== replacement) }))
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(currentTicket.legs.map((leg, index) => `${index + 1}. ${leg.match} | ${formatMarketName(leg.market)} @${formatOdds(leg.odds)}`).join('\n'))
    toast('Boleto copiado')
  }

  async function persistTicket(stakeAmount?: number) {
    const result = await addToTracking(currentTicket, stakeAmount)
    if (!result.saved) return
    onTrack?.(currentTicket)
    toast('Añadido a seguimiento', {
      description: `${ticket.legs.length} selecciones en seguimiento.`,
    })
  }

  function handleTrack() {
    if (isPro && bankroll) {
      setStakeDialogOpen(true)
      return
    }
    void persistTicket()
  }

  async function handleShare() {
    const result = await shareOrDownloadTicket(currentTicket)
    if (result === 'shared') toast('Boleto compartido')
    if (result === 'downloaded') toast('Imagen descargada')
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card ring-1 ring-white/5">
      {/* Mode accent strip — top 3px bar */}
      <div className={cn('h-[3px] w-full shrink-0 rounded-t-xl', meta.accent)} aria-hidden />

      {/* ── HEADER — mode badge + combined odds ── */}
      <div className="flex flex-col gap-3 p-4 pb-1">
        {/* Row 1: mode badge + combined odds */}
        <div className="flex items-center justify-between gap-3">
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold tracking-wide',
              meta.border,
              meta.bg,
              meta.text,
            )}
          >
            {meta.label}
          </span>

          <div className="flex flex-col items-end">
            <span className="font-mono text-4xl font-bold tabular-nums tracking-tight leading-none text-foreground">
              {formatOdds(currentTicket.legs.reduce((total, leg) => total * leg.odds, 1))}
            </span>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">Cuota Combinada</span>
              <button type="button" onClick={handleCopy} title="Copiar texto del boleto" aria-label="Copiar texto del boleto" className="flex size-6 cursor-pointer items-center justify-center rounded text-muted-foreground opacity-40 transition-opacity hover:bg-surface hover:text-foreground hover:opacity-100">
                <CopyIcon size={13} aria-hidden />
              </button>
            </div>
          </div>
        </div>

        <div className="my-2 grid grid-cols-3 divide-x divide-border/50 rounded-lg border border-border/60 bg-surface/30 px-3 py-2 text-center font-mono text-xs">
          <div className="flex flex-col gap-0.5 px-2">
            <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">Confianza IA</span>
            <span className="font-mono font-bold tabular-nums text-foreground">{ticket.confidence}%</span>
          </div>
          <div className="flex flex-col gap-0.5 px-2">
            <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">+EV Promedio</span>
            <span className="font-mono font-bold tabular-nums text-positive">{formatEV(currentTicket.legs.reduce((total, leg) => total + leg.ev, 0) / Math.max(currentTicket.legs.length, 1))}</span>
          </div>
          <div className="flex flex-col gap-0.5 px-2">
            <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">Rango</span>
            <span className="flex items-center gap-1 text-xs font-bold text-positive">
              <span className="size-1.5 rounded-full bg-positive" aria-hidden />
              En rango
            </span>
          </div>
        </div>
      </div>

      {/* ── LEGS — fills remaining vertical space ── */}
      {currentTicket.optimizedCount && (
        <div className="my-2 flex items-center gap-2 rounded-md border border-border/60 bg-surface/40 px-3.5 py-2 font-mono text-xs text-muted-foreground">
          Optimizado algorítmicamente: Reducimos tu boleto de {currentTicket.originalRequested} a {currentTicket.legs.length} selecciones para proteger tu Bankroll y mantener +EV real.
        </div>
      )}
      <ul className="flex flex-1 list-none flex-col px-4 pb-4">
        {currentTicket.legs.map((leg, i) => (
          <TicketLeg
            key={`${leg.match}-${leg.market}`}
            leg={leg}
            index={i}
            onSwap={() => swapLeg(i)}
            isPro={isPro}
            bankroll={bankroll}
            bankrollLoading={bankrollLoading}
            ticketKellyStake={currentTicket.kellyStake}
          />
        ))}
      </ul>

      {/* ── FOOTER — pinned to bottom ── */}
      <div className="mt-auto flex flex-col gap-2 border-t border-border/40 px-4 py-3">
        <Button id="generator-save-ticket" className="w-full cursor-pointer bg-primary py-3 text-xs font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90" onClick={handleTrack} disabled={isPro && bankrollLoading}>
          <StarIcon data-icon="inline-start" aria-hidden="true" />
          Guardar en Ledger Cuantitativo
        </Button>
        <button type="button" onClick={handleShare} className="mt-2 w-full rounded-lg border border-border bg-transparent py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-surface hover:text-foreground">
          <Share2 className="mr-2 inline-block size-3.5" aria-hidden /> Compartir / Descargar Imagen
        </button>
        <StatDisclaimer />
      </div>
      {bankroll && (
        <StakeConfirmDialog
          open={stakeDialogOpen}
          onOpenChange={setStakeDialogOpen}
          ticket={currentTicket}
          bankroll={bankroll}
          onConfirm={(stakeAmount) => persistTicket(stakeAmount)}
        />
      )}
    </div>
  )
}
