'use client'

import * as React from 'react'
import { Check, CircleAlert, Clock3, CreditCard, Sparkles } from 'lucide-react'
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
  refreshAuthSession,
  startSubscriptionTrial,
  type Subscription,
  type SubscriptionPlan,
} from '@/lib/subscriptions'
import type { WompiCardToken } from '@/lib/wompi'
import { cn } from '@/lib/utils'

const COMPARISON_ROWS = [
  ['Boletos generados', '2 por día (perfil EDGE)', 'Ilimitados, 3 perfiles'],
  ['Boletos guardados', '5 simultáneos', 'Ilimitados'],
  ['Mercados por partido', '10 de 56', 'Los 56 completos'],
  ['Bet Builder', '—', '✅'],
  ['Cartelera, 1X2, Resumen, H2H', '✅', '✅'],
] as const

const PLAN_LABELS: Record<SubscriptionPlan, string> = {
  mensual: 'Mensual',
  anual: 'Anual',
}

type PaymentState = 'idle' | 'submitting' | 'polling' | 'success' | 'rejected' | 'timeout'

function formatDate(value: string | null | undefined) {
  if (!value) return 'sin fecha definida'
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'long' }).format(new Date(value))
}

function statusLabel(subscription: Subscription) {
  if (subscription.status === 'trial') return 'Prueba gratis activa'
  if (subscription.status === 'pending_payment') return 'Pago pendiente de confirmación'
  if (subscription.status === 'active') return 'Suscripción activa'
  if (subscription.status === 'past_due') return 'Pago pendiente'
  if (subscription.status === 'cancelled') return 'Cancelada'
  return 'Reembolso solicitado'
}

function getErrorMessage(message: string) {
  return message || 'No se pudo completar la operación.'
}

function wait(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

export default function PlansPage() {
  const router = useRouter()
  const { user, isLoading: authLoading, refresh } = useAuthSession()
  const [subscription, setSubscription] = React.useState<Subscription | null>(null)
  const [subscriptionLoading, setSubscriptionLoading] = React.useState(true)
  const [trialLoading, setTrialLoading] = React.useState(false)
  const [activationPlan, setActivationPlan] = React.useState<SubscriptionPlan | null>(null)
  const [paymentState, setPaymentState] = React.useState<PaymentState>('idle')
  const [pageError, setPageError] = React.useState<string | null>(null)
  const [cancelOpen, setCancelOpen] = React.useState(false)
  const [cancelLoading, setCancelLoading] = React.useState(false)
  const autoTrialStarted = React.useRef(false)
  const autoActivationOpened = React.useRef(false)

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
    if (authLoading || !user || autoTrialStarted.current) return
    const action = new URLSearchParams(window.location.search).get('action')
    if (action !== 'trial') return
    autoTrialStarted.current = true
    void handleStartTrial()
  }, [authLoading, user])

  React.useEffect(() => {
    if (authLoading || !user || autoActivationOpened.current) return
    const plan = new URLSearchParams(window.location.search).get('activate')
    if (plan !== 'mensual' && plan !== 'anual') return
    autoActivationOpened.current = true
    setActivationPlan(plan)
  }, [authLoading, user])

  function redirectToTrialAfterAuth() {
    const redirect = encodeURIComponent('/planes?action=trial')
    router.push(`/cuenta/login?redirect=${redirect}`)
  }

  async function handleStartTrial() {
    setPageError(null)
    if (authLoading) return
    if (!user) {
      redirectToTrialAfterAuth()
      return
    }

    setTrialLoading(true)
    const result = await startSubscriptionTrial()
    if (!result.ok) {
      setPageError(getErrorMessage(result.error.message))
      setTrialLoading(false)
      return
    }

    setSubscription(result.data)
    refreshAuthSession()
    await refresh()
    toast.success('Tu prueba PRO está activa durante 7 días.')
    router.push('/')
  }

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
      return
    }

    setSubscription(result.data)
    setPaymentState('polling')
    await pollPaymentStatus()
  }

  async function pollPaymentStatus() {
    const deadline = Date.now() + 30_000
    while (Date.now() < deadline) {
      await wait(2_500)
      const result = await fetchSubscription()
      if (!result.ok) {
        setPaymentState('rejected')
        setPageError(result.error.message)
        return
      }

      setSubscription(result.data)
      if (result.data.status === 'active') {
        setPaymentState('success')
        refreshAuthSession()
        await refresh()
        toast.success('Tu suscripción PRO ya está activa.')
        router.push('/')
        return
      }

      const transaction = result.data.last_transaction
      const transactionRejected = transaction && ['DECLINED', 'ERROR', 'VOIDED'].includes(transaction.status)
      if (result.data.status !== 'pending_payment' || transactionRejected) {
        setPaymentState('rejected')
        const message = transaction?.status_message?.trim()
        const code = transaction?.processor_response_code?.trim()
        setPageError(message
          ? `El pago fue rechazado: ${message}${code ? ` (código ${code})` : ''}`
          : 'Wompi rechazó el pago y no entregó un motivo adicional.')
        return
      }
    }

    setPaymentState('timeout')
    setPageError('Tu pago está tardando en confirmarse. Revisa /planes más tarde; el estado se actualizará cuando Wompi confirme la operación.')
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

  const isActive = subscription?.status === 'active'
  const activationBusy = paymentState === 'submitting' || paymentState === 'polling'

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 py-6 sm:py-10">
        <section className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-brand">BetMind PRO</p>
          <h1 className="mt-4 font-serif text-4xl leading-tight tracking-tight text-foreground sm:text-6xl">Apuesta con la misma información que la casa.</h1>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground">7 días gratis, sin tarjeta. Cancelá cuando quieras.</p>
        </section>

        {pageError && (
          <div role="alert" className="flex items-start gap-3 rounded-xl border border-negative/30 bg-negative/10 px-4 py-3 text-sm text-negative">
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <p>{pageError}</p>
          </div>
        )}

        {user && subscription && <SubscriptionStatusCard subscription={subscription} onCancel={() => setCancelOpen(true)} />}

        <section aria-label="Planes BetMind PRO" className="grid gap-4 md:grid-cols-2">
          <PlanCard
            title="Mensual"
            plan="mensual"
            price="COP 29.900 /mes"
            description="Facturación mensual, cancelá cuando quieras."
            onStart={handleStartTrial}
            onActivate={openActivation}
            subscription={subscription}
            loading={trialLoading || subscriptionLoading}
          />
          <PlanCard
            recommended
            title="Anual"
            plan="anual"
            price="COP 249.900 /año"
            description="Facturación anual, mismo acceso PRO completo."
            detail="equivalente a COP 20.825/mes"
            onStart={handleStartTrial}
            onActivate={openActivation}
            subscription={subscription}
            loading={trialLoading || subscriptionLoading}
          />
        </section>

        {activationPlan && !isActive && (
          <section aria-labelledby="payment-title" className="rounded-2xl border border-brand/30 bg-card p-5 shadow-xl shadow-brand/5 sm:p-7">
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand">Activación segura</p>
                <h2 id="payment-title" className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Activar plan {PLAN_LABELS[activationPlan]}</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">Tu tarjeta se tokeniza directamente con Wompi. El cobro se confirma después de que el banco procese la operación.</p>
              </div>
              {!activationBusy && <button type="button" onClick={() => setActivationPlan(null)} className="text-xs font-semibold text-muted-foreground transition-colors hover:text-foreground">Cerrar</button>}
            </div>

            {paymentState === 'polling' || paymentState === 'submitting' ? (
              <div className="flex items-center gap-3 rounded-xl border border-brand/20 bg-brand/5 px-4 py-4 text-sm font-semibold text-foreground">
                <Clock3 className="size-5 animate-pulse text-brand" aria-hidden="true" />
                {paymentState === 'submitting' ? 'Registrando tu pago...' : 'Confirmando tu pago...'}
              </div>
            ) : paymentState === 'timeout' ? (
              <div className="rounded-xl border border-warning/30 bg-warning/10 px-4 py-4 text-sm text-foreground">Revisa esta página más tarde para ver el estado final de tu pago.</div>
            ) : (
              <WompiCardForm onTokenized={handleTokenizedCard} disabled={paymentState === 'success'} />
            )}
          </section>
        )}

        {!user && <p className="mx-auto max-w-xl text-center text-xs leading-5 text-subtle">Para activar una suscripción necesitás una cuenta. El trial se inicia después de iniciar sesión o crearla.</p>}
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
    </AppShell>
  )
}

function SubscriptionStatusCard({ subscription, onCancel }: { subscription: Subscription; onCancel: () => void }) {
  const isTrial = subscription.status === 'trial'
  const periodLabel = isTrial ? 'Fin de la prueba' : 'Próxima renovación / fin de período'
  return (
    <section aria-labelledby="subscription-status-title" className="rounded-2xl border border-positive/25 bg-positive/5 p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-positive/15 text-positive"><CreditCard className="size-5" aria-hidden="true" /></div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-positive">Tu suscripción</p>
            <h2 id="subscription-status-title" className="mt-1 text-lg font-semibold text-foreground">{statusLabel(subscription)} · {PLAN_LABELS[subscription.plan]}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{periodLabel}: {formatDate(isTrial ? subscription.trial_ends_at : subscription.current_period_end)}</p>
          </div>
        </div>
        {subscription.status === 'active' && <button type="button" onClick={onCancel} className="inline-flex min-h-10 items-center justify-center rounded-lg border border-negative/30 px-3 text-xs font-semibold text-negative transition-colors hover:bg-negative/10">Cancelar suscripción</button>}
      </div>
    </section>
  )
}

function PlanCard({ title, plan, price, description, detail, recommended = false, onStart, onActivate, subscription, loading }: { title: string; plan: SubscriptionPlan; price: string; description: string; detail?: string; recommended?: boolean; onStart: () => void; onActivate: (plan: SubscriptionPlan) => void; subscription: Subscription | null; loading: boolean }) {
  const isActive = subscription?.status === 'active'
  const isPending = subscription?.status === 'pending_payment'
  return (
    <article className={cn('relative flex flex-col rounded-2xl border bg-card p-6', recommended ? 'border-brand/60 shadow-xl shadow-brand/10' : 'border-border')}>
      {recommended && <span className="absolute -top-3 right-5 inline-flex items-center gap-1 rounded-full bg-brand px-3 py-1 text-[10px] font-bold text-primary-foreground"><Sparkles size={12} aria-hidden="true" /> Ahorra 2 meses</span>}
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-subtle">{title}</p>
      <p className="mt-4 text-2xl font-bold tracking-tight text-foreground">{price}</p>
      {detail && <p className="mt-1 text-xs text-brand">{detail}</p>}
      <p className="mt-3 min-h-10 text-sm leading-6 text-muted-foreground">{description}</p>
      <button type="button" onClick={onStart} disabled={loading || isActive || isPending} className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-brand px-4 text-sm font-bold text-primary-foreground transition-[transform,opacity] duration-150 hover:opacity-90 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:opacity-50"><Check size={16} aria-hidden="true" /> {isActive ? 'Plan activo' : isPending ? 'Pago pendiente' : 'Empezar prueba gratis'}</button>
      {!isActive && !isPending && <button type="button" onClick={() => onActivate(plan)} disabled={loading} className="mt-2 inline-flex min-h-10 items-center justify-center rounded-xl border border-border px-4 text-xs font-semibold text-muted-foreground transition-[transform,color] duration-150 hover:text-foreground active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50">{subscription?.status === 'trial' ? `Activar ${title}` : `Pagar ${title} directamente`}</button>}
    </article>
  )
}
