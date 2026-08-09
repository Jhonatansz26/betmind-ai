'use client'

import * as React from 'react'
import { Check, Sparkles } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

import { AppShell } from '@/components/betmind/app-shell'
import { setDevProFlag } from '@/lib/subscription'
import { cn } from '@/lib/utils'

const COMPARISON_ROWS = [
  ['Boletos generados', '2 por día (perfil EDGE)', 'Ilimitados, 3 perfiles'],
  ['Boletos guardados', '5 simultáneos', 'Ilimitados'],
  ['Mercados por partido', '10 de 56', 'Los 56 completos'],
  ['Bet Builder', '—', '✅'],
  ['Cartelera, 1X2, Resumen, H2H', '✅', '✅'],
] as const

export default function PlansPage() {
  const router = useRouter()

  function startTrial() {
    // TODO(backend-pagos): reemplazar por integración real de Wompi (checkout, webhook de confirmación, creación de suscripción)
    setDevProFlag(true)
    toast('Modo PRO simulado activado — esto es una demostración, todavía no hay cobro real.')
    router.push('/')
  }

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-12 py-6 sm:py-10">
        <section className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-brand">BetMind PRO</p>
          <h1 className="mt-4 font-serif text-4xl leading-tight tracking-tight text-foreground sm:text-6xl">Apuesta con la misma información que la casa.</h1>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground">7 días gratis, sin tarjeta. Cancelá cuando quieras.</p>
        </section>

        <section aria-label="Planes BetMind PRO" className="grid gap-4 md:grid-cols-2">
          <PlanCard title="Mensual" price="COP 29.900 /mes" description="Facturación mensual, cancelá cuando quieras." onStart={startTrial} />
          <PlanCard recommended title="Anual" price="COP 249.900 /año" description="Facturación anual, mismo acceso PRO completo." detail="equivalente a COP 20.825/mes" onStart={startTrial} />
        </section>

        <p className="mx-auto max-w-3xl text-center text-xs leading-5 text-subtle">Sin tarjeta durante los 7 días de prueba. Si decidís continuar y no te convence, te devolvemos tu dinero dentro de los primeros 7 días de pago.</p>

        <section aria-labelledby="comparison-title" className="flex flex-col gap-4">
          <div className="text-center"><h2 id="comparison-title" className="text-xl font-semibold text-foreground">Todo lo que desbloqueás</h2><p className="mt-1 text-sm text-muted-foreground">Empezá gratis y pasá a PRO cuando quieras más profundidad.</p></div>
          <div className="overflow-hidden rounded-2xl border border-border bg-card">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-surface-raised/60"><tr><th className="px-4 py-4 font-semibold text-foreground sm:px-6">Funcionalidad</th><th className="px-4 py-4 text-center font-semibold text-muted-foreground sm:px-6">Free</th><th className="px-4 py-4 text-center font-semibold text-brand sm:px-6">PRO</th></tr></thead>
              <tbody>{COMPARISON_ROWS.map(([feature, free, pro]) => <tr key={feature} className="border-b border-border/60 last:border-0"><th scope="row" className="px-4 py-4 font-medium text-foreground sm:px-6">{feature}</th><td className="px-4 py-4 text-center text-muted-foreground sm:px-6">{free}</td><td className="px-4 py-4 text-center font-medium text-foreground sm:px-6">{pro}</td></tr>)}</tbody>
            </table>
          </div>
        </section>
      </div>
    </AppShell>
  )
}

function PlanCard({ title, price, description, detail, recommended = false, onStart }: { title: string; price: string; description: string; detail?: string; recommended?: boolean; onStart: () => void }) {
  return (
    <article className={cn('relative flex flex-col rounded-2xl border bg-card p-6', recommended ? 'border-brand/60 shadow-xl shadow-brand/10' : 'border-border')}>
      {recommended && <span className="absolute -top-3 right-5 inline-flex items-center gap-1 rounded-full bg-brand px-3 py-1 text-[10px] font-bold text-primary-foreground"><Sparkles size={12} aria-hidden="true" /> Ahorra 2 meses</span>}
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-subtle">{title}</p>
      <p className="mt-4 text-2xl font-bold tracking-tight text-foreground">{price}</p>
      {detail && <p className="mt-1 text-xs text-brand">{detail}</p>}
      <p className="mt-3 min-h-10 text-sm leading-6 text-muted-foreground">{description}</p>
      <button type="button" onClick={onStart} className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-brand px-4 text-sm font-bold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"><Check size={16} aria-hidden="true" /> Empezar prueba gratis</button>
    </article>
  )
}
