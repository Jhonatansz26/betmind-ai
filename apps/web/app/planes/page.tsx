'use client'

import * as React from 'react'
import { Check, CircleAlert, CreditCard, Loader2, Sparkles } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

import { AppShell } from '@/components/betmind/app-shell'
import { WompiCardForm } from '@/components/betmind/wompi-card-form'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useAuthSession } from '@/lib/hooks/use-auth-session'
import {
  activateSubscription,
  cancelSubscription,
  fetchSubscription,
  requestRefund,
  refreshAuthSession,
  type Subscription,
  type SubscriptionPlan,
} from '@/lib/subscriptions'
import type { WompiCardToken } from '@/lib/wompi'
import { cn } from '@/lib/utils'

const COMPARISON_ROWS = [
  ['Boletos generados', '2 por día (perfil EDGE)', 'Ilimitados, 3 perfiles'],
  ['Boletos guardados', '5 simultáneos', 'Ilimitados'],
  ['Mercados por partido', '10 mercados', 'Catálogo completo'],
  ['Bet Builder', '—', '✅'],
  ['Cartelera, 1X2, Resumen, H2H', '✅', '✅'],
] as const

const PLAN_LABELS: Record<SubscriptionPlan, string> = {
  mensual: 'Mensual',
  anual: 'Anual',
}

type PaymentState = 'idle' | 'submitting' | 'success' | 'rejected'

function formatDate(value: string | null | undefined) {
  if (!value) return 'sin fecha definida'
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'long' }).format(new Date(value))
}

function statusLabel(subscription: Subscription) {
  if (subscription.status === 'pending_payment') return 'Pago pendiente de confirmación'
  if (subscription.status === 'active') return 'Suscripción activa'
  if (subscription.status === 'past_due') return 'Pago pendiente'
  if (subscription.status === 'cancelled') return 'Cancelada'
  if (subscription.status === 'refund_requested') return 'Reembolso solicitado'
  return 'Acceso PRO en verificación'
}

function getErrorMessage(message: string) {
  return message || 'No se pudo completar la operación.'
}

export default function PlansPage() {
  const router = useRouter()
  const { user, isLoading: authLoading, refresh } = useAuthSession()
  const [subscription, setSubscription] = React.useState<Subscription | null>(null)
  const [subscriptionLoading, setSubscriptionLoading] = React.useState(true)
  const [activationPlan, setActivationPlan] = React.useState<SubscriptionPlan | null>(null)
  const [paymentState, setPaymentState] = React.useState<PaymentState>('idle')
  const [pageError, setPageError] = React.useState<string | null>(null)
  const [cancelOpen, setCancelOpen] = React.useState(false)
  const [cancelLoading, setCancelLoading] = React.useState(false)
  const [refundOpen, setRefundOpen] = React.useState(false)
  const [refundLoading, setRefundLoading] = React.useState(false)
  const autoActivationOpened = React.useRef(false)
  const redirectTimerRef = React.useRef<number | null>(null)

  React.useEffect(() => () => {
    if (redirectTimerRef.current !== null) window.clearTimeout(redirectTimerRef.current)
  }, [])

  React.useEffect(() => {
    if (authLoading) return
    let active = true
    if (!user) {
      setSubscription(null)
      setSubscriptionLoading(false)
      return () => {
        active = false
      }
    }

    setSubscriptionLoading(true)
    void fetchSubscription().then((result) => {
      if (!active) return
      if (result.ok) {
        setSubscription(result.data)
      } else if (result.error.code !== 'HTTP_404') {
        setPageError(result.error.message)
      }
    }).finally(() => {
      if (active) setSubscriptionLoading(false)
    })

    return () => {
      active = false
    }
  }, [authLoading, user])

  React.useEffect(() => {
    if (authLoading || !user || autoActivationOpened.current) return
    const plan = new URLSearchParams(window.location.search).get('activate')
    if (plan !== 'mensual' && plan !== 'anual') return
    autoActivationOpened.current = true
    setActivationPlan(plan)
  }, [authLoading, user])

  function openActivation(plan: SubscriptionPlan) {
    setPageError(null)
    setPaymentState('idle')
    if (!user) {
      const redirect = encodeURIComponent(`/planes?activate=${plan}`)
      router.push(`/cuenta/login?redirect=${redirect}`)
      return
    }
    setActivationPlan(plan)
  }

  async function handleTokenizedCard(token: WompiCardToken) {
    if (!activationPlan) return
    setPageError(null)
    setPaymentState('submitting')
    const result = await activateSubscription(
      token.card_token,
      activationPlan,
      token.acceptance_token,
      token.accept_personal_auth,
    )

    if (!result.ok) {
      setPaymentState('rejected')
      setPageError(getErrorMessage(result.error.message))
      toast.error(getErrorMessage(result.error.message))
      return
    }

    setSubscription(result.data)
    // La sesión es best-effort: el pago ya quedó registrado en PENDING y el
    // webhook de Wompi confirmará la suscripción. Un fallo del refresh (red,
    // timeout) no debe dejar la UI congelada en "Procesando pago...".
    try {
      refreshAuthSession()
      await refresh()
    } catch {
      // Ignorado a propósito: la activación ya fue confirmada por la API.
    }
    setPaymentState('success')
    redirectTimerRef.current = window.setTimeout(() => router.push('/'), 2_500)
  }

  async function handleCancel() {
    setCancelLoading(true)
    setPageError(null)
    const result = await cancelSubscription()
    setCancelLoading(false)
    if (!result.ok) {
      setPageError(result.error.message)
      return
    }
    setSubscription(result.data)
    setCancelOpen(false)
    refreshAuthSession()
    await refresh()
    toast.success(`Tu suscripción fue cancelada. Vas a mantener acceso PRO hasta el ${formatDate(result.data.current_period_end)}.`)
  }

  async function handleRefund() {
    setRefundLoading(true)
    setPageError(null)
    const result = await requestRefund()
    setRefundLoading(false)
    if (!result.ok) {
      setPageError(result.error.message)
      return
    }
    setSubscription(result.data)
    setRefundOpen(false)
    refreshAuthSession()
    await refresh()
    toast.success('Tu acceso PRO fue revocado de inmediato. El reembolso del dinero se procesa por separado y no es instantáneo.')
  }

  const isActive = subscription?.status === 'active'
  const refundEligible = subscription?.refund_eligible ?? false

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 py-6 sm:py-10">
        <section className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-brand">BetMind PRO</p>
          <h1 className="mt-4 font-serif text-4xl leading-tight tracking-tight text-foreground sm:text-6xl">Apuesta con la misma información que la casa.</h1>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground">Acceso free con límites claros. Desbloqueá el terminal completo cuando estés listo.</p>
        </section>

        {pageError && (
          <div role="alert" className="flex items-start gap-3 rounded-xl border border-negative/30 bg-negative/10 px-4 py-3 text-sm text-negative">
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <p>{pageError}</p>
          </div>
        )}

         {user && subscription && <SubscriptionStatusCard subscription={subscription} onCancel={() => setCancelOpen(true)} onRefund={() => setRefundOpen(true)} refundEligible={refundEligible} />}

        <section aria-label="Planes BetMind PRO" className="grid gap-4 md:grid-cols-2">
          <PlanCard
            title="Mensual"
            plan="mensual"
            price="COP 29.900 /mes"
            description="Facturación mensual, cancelá cuando quieras."
            cta="Desbloquear Terminal VIP - COP 29.900/mes"
            onActivate={openActivation}
            subscription={subscription}
            loading={subscriptionLoading}
          />
          <PlanCard
            recommended
            title="Anual"
            plan="anual"
            price="COP 249.900 /año"
            description="Facturación anual, mismo acceso PRO completo."
            detail="equivalente a COP 20.825/mes"
            cta="Desbloquear VIP Anual - COP 249.900 (Ahorra 2 meses)"
            onActivate={openActivation}
            subscription={subscription}
            loading={subscriptionLoading}
          />
        </section>

        {activationPlan && !isActive && (
          <section aria-labelledby="payment-title" className="rounded-2xl border border-brand/30 bg-card p-5 shadow-xl shadow-brand/5 sm:p-7">
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand">Activación segura</p>
                <h2 id="payment-title" className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Activar plan {PLAN_LABELS[activationPlan]}</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">Los datos de tu tarjeta se capturan en los elementos seguros de Wompi (PCI DSS). El cobro se confirma cuando Wompi procesa la operación.</p>
              </div>
              {paymentState === 'idle' && <button type="button" onClick={() => setActivationPlan(null)} className="text-xs font-semibold text-muted-foreground transition-colors hover:text-foreground">Cerrar</button>}
            </div>

            {paymentState === 'submitting' ? (
              <div className="flex items-center gap-3 rounded-xl border border-brand/20 bg-brand/5 px-4 py-4 text-sm font-semibold text-foreground">
                <Loader2 className="size-5 animate-spin text-brand" aria-hidden="true" />
                Procesando pago...
              </div>
            ) : paymentState === 'success' ? (
              <div className="flex flex-col items-center gap-4 rounded-xl border border-positive/25 bg-positive/5 px-6 py-10 text-center">
                <Loader2 className="size-6 animate-spin text-brand" aria-hidden="true" />
                <p className="text-sm font-semibold text-foreground">Transacción en proceso. Tu terminal VIP se activará en breve.</p>
                <p className="text-xs leading-5 text-muted-foreground">Te redirigimos al dashboard en unos segundos.</p>
              </div>
            ) : (
              <WompiCardForm plan={activationPlan} onTokenized={handleTokenizedCard} />
            )}
          </section>
        )}

        {!user && <p className="mx-auto max-w-xl text-center text-xs leading-5 text-subtle">Para activar una suscripción necesitás una cuenta. El checkout de Wompi se abre después de iniciar sesión o crearla.</p>}
        <p className="mx-auto max-w-3xl text-center text-xs leading-5 text-subtle">Sin permanencia. Si te suscribís y no te convence, te devolvemos tu dinero dentro de los primeros 7 días de pago.</p>

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

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Cancelar suscripción?</DialogTitle>
            <DialogDescription>Vas a conservar el acceso PRO hasta el {formatDate(subscription?.current_period_end)}. Después de esa fecha no se realizará una nueva renovación.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button" onClick={() => setCancelOpen(false)} disabled={cancelLoading} className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border px-3 text-xs font-semibold text-foreground transition-colors hover:bg-surface disabled:opacity-50">Volver</button>
            <button type="button" onClick={() => void handleCancel()} disabled={cancelLoading} className="inline-flex min-h-10 items-center justify-center rounded-lg bg-negative px-3 text-xs font-semibold text-white transition-[transform,opacity] duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-50">{cancelLoading ? 'Cancelando...' : 'Sí, cancelar'}</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={refundOpen} onOpenChange={setRefundOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Solicitar reembolso?</DialogTitle>
            <DialogDescription>
              Esta acción revoca tu acceso PRO de inmediato. La solicitud de devolución del dinero se procesa por separado y puede tardar; no es un reembolso instantáneo.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button" onClick={() => setRefundOpen(false)} disabled={refundLoading} className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border px-3 text-xs font-semibold text-foreground transition-colors hover:bg-surface disabled:opacity-50">Volver</button>
            <button type="button" onClick={() => void handleRefund()} disabled={refundLoading} className="inline-flex min-h-10 items-center justify-center rounded-lg bg-negative px-3 text-xs font-semibold text-white transition-[transform,opacity] duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-50">{refundLoading ? 'Solicitando…' : 'Sí, solicitar reembolso'}</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

function SubscriptionStatusCard({ subscription, onCancel, onRefund, refundEligible }: { subscription: Subscription; onCancel: () => void; onRefund: () => void; refundEligible: boolean }) {
  const periodLabel = 'Próxima renovación / fin de período'
  return (
    <section aria-labelledby="subscription-status-title" className="rounded-2xl border border-positive/25 bg-positive/5 p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-positive/15 text-positive"><CreditCard className="size-5" aria-hidden="true" /></div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-positive">Tu suscripción</p>
            <h2 id="subscription-status-title" className="mt-1 text-lg font-semibold text-foreground">{statusLabel(subscription)} · {PLAN_LABELS[subscription.plan]}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{periodLabel}: {formatDate(subscription.current_period_end)}</p>
          </div>
        </div>
        {subscription.status === 'active' && <div className="flex flex-wrap gap-2">
          {refundEligible && <button type="button" onClick={onRefund} className="inline-flex min-h-10 items-center justify-center rounded-lg border border-negative/30 px-3 text-xs font-semibold text-negative transition-colors hover:bg-negative/10">Solicitar reembolso</button>}
          <button type="button" onClick={onCancel} className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border px-3 text-xs font-semibold text-muted-foreground transition-colors hover:bg-surface hover:text-foreground">Cancelar suscripción</button>
        </div>}
      </div>
    </section>
  )
}

function PlanCard({ title, plan, price, description, detail, cta, recommended = false, onActivate, subscription, loading }: { title: string; plan: SubscriptionPlan; price: string; description: string; detail?: string; cta: string; recommended?: boolean; onActivate: (plan: SubscriptionPlan) => void; subscription: Subscription | null; loading: boolean }) {
  const isActive = subscription?.status === 'active'
  const isPending = subscription?.status === 'pending_payment'
  return (
    <article className={cn('relative flex flex-col rounded-2xl border bg-card p-6', recommended ? 'border-brand/60 shadow-xl shadow-brand/10' : 'border-border')}>
      {recommended && <span className="absolute -top-3 right-5 inline-flex items-center gap-1 rounded-full bg-brand px-3 py-1 text-[10px] font-bold text-primary-foreground"><Sparkles size={12} aria-hidden="true" /> Ahorra 2 meses</span>}
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-subtle">{title}</p>
      <p className="mt-4 text-2xl font-bold tracking-tight text-foreground">{price}</p>
      {detail && <p className="mt-1 text-xs text-brand">{detail}</p>}
      <p className="mt-3 min-h-10 text-sm leading-6 text-muted-foreground">{description}</p>
      <button type="button" onClick={() => onActivate(plan)} disabled={loading || isActive || isPending} className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-brand px-4 text-sm font-bold text-primary-foreground transition-[transform,opacity] duration-150 hover:opacity-90 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:opacity-50"><Check size={16} aria-hidden="true" /> {isActive ? 'Plan activo' : isPending ? 'Pago pendiente' : cta}</button>
    </article>
  )
}
