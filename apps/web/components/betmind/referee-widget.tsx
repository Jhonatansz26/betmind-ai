'use client'

import * as React from 'react'
import { toast } from 'sonner'
import type { Referee } from '@/lib/betmind'

function RefereePending() {
  const [notified, setNotified] = React.useState(false)
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4 text-xs">
      <div>
        <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">FACTOR AMBIENTAL • ÁRBITRO</p>
        <p className="mt-2 text-sm font-semibold text-foreground">Árbitro pendiente de confirmación</p>
        <p className="mt-1 leading-relaxed text-muted-foreground">Normalmente se confirma 4–6 horas antes del partido.</p>
      </div>
      <button type="button" disabled={notified} onClick={() => { setNotified(true); toast.success('Notificación activada', { description: 'Te avisaremos cuando se confirme el árbitro.' }) }} className="w-fit rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-surface hover:text-foreground disabled:opacity-60">
        {notified ? 'Notificación activada' : 'Notificarme cuando se confirme'}
      </button>
    </div>
  )
}

function RefereeProfile({ referee }: { referee: Referee }) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4 text-xs">
      <div className="flex items-start justify-between gap-3 border-b border-border/50 pb-3">
        <div>
          <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">FACTOR AMBIENTAL • ÁRBITRO</p>
          <p className="mt-2 text-sm font-semibold text-foreground">{referee.name}</p>
        </div>
        <div className="text-right">
          <span className="block font-mono text-xs font-bold tabular-nums text-foreground">{referee.strictness}/100</span>
          <span className="text-[10px] text-muted-foreground">Rigurosidad</span>
        </div>
      </div>
      <div className="grid grid-cols-2 divide-x divide-y divide-border/50 rounded border border-border/50 bg-surface/30">
        <div className="p-2.5"><span className="block text-[10px] text-muted-foreground">Partidos clave</span><span className="font-mono text-xs font-bold tabular-nums text-foreground">{referee.highStakes.toFixed(0)}</span></div>
        <div className="p-2.5"><span className="block text-[10px] text-muted-foreground">Tendencia</span><span className="text-xs font-semibold text-foreground">{referee.trend}</span></div>
        <div className="p-2.5"><span className="block text-[10px] text-muted-foreground">Amarillas / partido</span><span className="font-mono text-xs font-bold tabular-nums text-foreground">{referee.yellows.toFixed(1)}</span></div>
        <div className="p-2.5"><span className="block text-[10px] text-muted-foreground">Rojas / partido</span><span className="font-mono text-xs font-bold tabular-nums text-foreground">{referee.reds.toFixed(2)}</span></div>
      </div>
    </div>
  )
}

export function RefereeWidget({ referee }: { referee: Referee }) {
  return referee.name === 'Por confirmar' ? <RefereePending /> : <RefereeProfile referee={referee} />
}
