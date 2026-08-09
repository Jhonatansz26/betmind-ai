'use client'

import * as React from 'react'

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { Bankroll } from '@/lib/bankroll'
import type { Ticket } from '@/lib/betmind'
import { formatCOP, formatCOPInput, parseCOPInput } from '@/lib/formatters'
import { Button } from '@/components/ui/button'

export function StakeConfirmDialog({
  open,
  onOpenChange,
  ticket,
  bankroll,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  ticket: Ticket
  bankroll: Bankroll
  onConfirm: (stakeAmount: number) => Promise<void>
}) {
  const suggestedAmount = ticket.kellyStake != null
    ? bankroll.current_capital * ticket.kellyStake
    : null
  const [input, setInput] = React.useState('')
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    if (!open) return
    setInput(suggestedAmount != null ? formatCOPInput(suggestedAmount) : '')
    setError(null)
  }, [open, suggestedAmount])

  async function handleConfirm() {
    const amount = parseCOPInput(input)
    if (amount == null || amount < 0) {
      setError('Ingresá un monto de apuesta igual o mayor a $0.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onConfirm(amount)
      onOpenChange(false)
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : 'No se pudo guardar el boleto.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirmá tu stake</DialogTitle>
          <DialogDescription>
            Tu bankroll actual es {formatCOP(bankroll.current_capital)}. Ajustá cuánto vas a arriesgar antes de guardar este boleto.
          </DialogDescription>
        </DialogHeader>
        <label className="flex flex-col gap-2 text-xs font-semibold text-foreground">
          Monto real de la apuesta
          <div className="flex items-center rounded-lg border border-border bg-surface px-3 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
            <span className="font-mono text-sm text-muted-foreground">$</span>
            <input
              autoFocus
              inputMode="numeric"
              value={input}
              onChange={(event) => {
                const raw = event.target.value
                const parsed = parseCOPInput(raw)
                setInput(parsed == null ? (raw.includes('-') ? '-' : '') : formatCOPInput(parsed))
              }}
              className="min-h-11 w-full bg-transparent px-2 text-right font-mono text-lg font-bold tabular-nums text-foreground outline-none"
              aria-label="Monto real de la apuesta en pesos colombianos"
            />
          </div>
        </label>
        {suggestedAmount != null ? (
          <p className="text-xs leading-5 text-muted-foreground">
            Sugerencia Kelly del boleto: <span className="font-mono font-semibold text-primary">{formatCOP(suggestedAmount)}</span> ({(ticket.kellyStake! * 100).toFixed(1)}%).
          </p>
        ) : (
          <p className="text-xs leading-5 text-muted-foreground">Este boleto no trae una sugerencia Kelly agregada. Completá el monto manualmente.</p>
        )}
        {error && <p role="alert" className="rounded-lg border border-negative/30 bg-negative/10 px-3 py-2 text-xs leading-5 text-negative">{error}</p>}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>Cancelar</Button>
          <Button type="button" onClick={() => void handleConfirm()} disabled={saving}>{saving ? 'Guardando…' : 'Guardar boleto'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
