'use client'

import * as React from 'react'
import { CreditCard, Loader2, LockKeyhole } from 'lucide-react'
import { toast } from 'sonner'

import type { SubscriptionPlan } from '@/lib/subscriptions'
import { fetchWompiAcceptance, type WompiCardToken } from '@/lib/wompi'

const WOMPI_WIDGET_URL = (process.env.NEXT_PUBLIC_WOMPI_WIDGET_URL ?? 'https://checkout.wompi.co/widget.js').replace(/\/$/, '')
const WOMPI_PUBLIC_KEY = process.env.NEXT_PUBLIC_WOMPI_PUB_KEY ?? process.env.NEXT_PUBLIC_WOMPI_PUBLIC_KEY ?? ''

const AMOUNT_IN_CENTS: Record<SubscriptionPlan, number> = {
  mensual: 2_990_000,
  anual: 24_990_000,
}

interface WompiWidgetConfig {
  publicKey: string
  currency: 'COP'
  amountInCents: number
  reference: string
  widgetOperation: 'tokenize'
}

interface WompiPaymentSource {
  type?: string
  token?: string
  card_token?: string
  id?: string
  acceptance_token?: string
  accept_personal_auth?: string
}

interface WompiWidgetCallbackData {
  payment_source?: WompiPaymentSource
  transaction?: unknown
}

interface WidgetCheckoutInstance {
  open: (callback?: (data: WompiWidgetCallbackData) => void) => void
  renderPurchaseButton: (container: HTMLElement) => void
  renderTokenizeButton: (container: HTMLElement) => void
}

declare global {
  interface Window {
    WidgetCheckout?: new (config: WompiWidgetConfig) => WidgetCheckoutInstance
  }
}

interface WompiCardFormProps {
  plan: SubscriptionPlan
  onTokenized: (result: WompiCardToken) => void
}

interface WompiAcceptanceTokens {
  acceptance_token: string
  accept_personal_auth: string
}

function loadWompiWidget(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined') {
      reject(new Error('El checkout seguro de Wompi solo se ejecuta en el navegador.'))
      return
    }
    if (window.WidgetCheckout) {
      resolve()
      return
    }
    const existing = document.querySelector<HTMLScriptElement>('script[data-betmind-wompi-widget]')
    if (existing) {
      const handleLoad = () => {
        existing.removeEventListener('load', handleLoad)
        existing.removeEventListener('error', handleError)
        if (window.WidgetCheckout) resolve()
        else reject(new Error('Wompi no inicializó correctamente.'))
      }
      const handleError = () => {
        existing.removeEventListener('load', handleLoad)
        existing.removeEventListener('error', handleError)
        reject(new Error('No se pudo cargar el checkout seguro de Wompi.'))
      }
      existing.addEventListener('load', handleLoad)
      existing.addEventListener('error', handleError)
      return
    }
    const script = document.createElement('script')
    script.src = WOMPI_WIDGET_URL
    script.async = true
    script.dataset.betmindWompiWidget = 'true'
    script.addEventListener('load', () => {
      if (window.WidgetCheckout) resolve()
      else reject(new Error('Wompi no inicializó correctamente.'))
    })
    script.addEventListener('error', () => reject(new Error('No se pudo cargar el checkout seguro de Wompi.')))
    document.body.appendChild(script)
  })
}

export function WompiCardForm({ plan, onTokenized }: WompiCardFormProps) {
  const [scriptState, setScriptState] = React.useState<'loading' | 'ready' | 'error'>('loading')
  const [scriptError, setScriptError] = React.useState<string | null>(null)
  const [bootAttempt, setBootAttempt] = React.useState(0)
  const openInFlight = React.useRef(false)
  const acceptanceRef = React.useRef<WompiAcceptanceTokens | null>(null)

  React.useEffect(() => {
    let active = true
    fetchWompiAcceptance()
      .then((data) => {
        const tokens: WompiAcceptanceTokens = {
          acceptance_token: data.presigned_acceptance.acceptance_token,
          accept_personal_auth: data.presigned_personal_data_auth.acceptance_token,
        }
        acceptanceRef.current = tokens
      })
      .catch((reason: unknown) => {
        console.warn('Wompi acceptance tokens no disponibles: ' + (reason instanceof Error ? reason.message : String(reason)))
      })
    return () => {
      active = false
    }
  }, [])

  React.useEffect(() => {
    if (!WOMPI_PUBLIC_KEY) {
      setScriptState('error')
      setScriptError('La llave pública de Wompi no está configurada en el frontend.')
      return
    }
    let active = true
    setScriptState('loading')
    setScriptError(null)
    loadWompiWidget()
      .then(() => {
        if (active) setScriptState('ready')
      })
      .catch((reason: unknown) => {
        if (!active) return
        setScriptState('error')
        setScriptError(reason instanceof Error ? reason.message : 'No se pudo cargar el checkout seguro de Wompi.')
      })
    return () => {
      active = false
    }
  }, [bootAttempt])

  React.useEffect(() => {
    const reset = () => {
      openInFlight.current = false
    }
    const events = ['escpressed', 'merchantreturnclicked', 'merchantcontinueclicked', 'finishtokenization']
    events.forEach((name) => document.addEventListener(name, reset))
    return () => events.forEach((name) => document.removeEventListener(name, reset))
  }, [])

  function openWompiCheckout() {
    if (openInFlight.current || !window.WidgetCheckout) return
    openInFlight.current = true
    let widget: WidgetCheckoutInstance
    try {
      widget = new window.WidgetCheckout({
        publicKey: WOMPI_PUBLIC_KEY,
        currency: 'COP',
        amountInCents: AMOUNT_IN_CENTS[plan],
        reference: `BM-${Date.now()}`,
        widgetOperation: 'tokenize',
      })
    } catch (reason: unknown) {
      openInFlight.current = false
      toast.error(reason instanceof Error ? reason.message : 'Wompi no pudo inicializar el checkout.')
      return
    }
    widget.open((data) => {
      openInFlight.current = false
      const source = data?.payment_source
      const cardToken = source?.token ?? source?.card_token ?? source?.id
      const acceptanceToken = source?.acceptance_token ?? acceptanceRef.current?.acceptance_token
      const acceptPersonalAuth = source?.accept_personal_auth ?? acceptanceRef.current?.accept_personal_auth
      if (!cardToken || !acceptanceToken || !acceptPersonalAuth) {
        toast.error('Wompi no entregó un token válido para esta tarjeta. Intentá de nuevo.')
        return
      }
      onTokenized({
        card_token: cardToken,
        acceptance_token: acceptanceToken,
        accept_personal_auth: acceptPersonalAuth,
      })
    })
  }

  if (scriptState === 'loading') {
    return (
      <div role="status" aria-live="polite" className="flex min-h-52 flex-col items-center justify-center gap-3 rounded-xl border border-brand/20 bg-surface/30 px-6 py-10 text-center">
        <Loader2 className="size-6 animate-spin text-brand" aria-hidden="true" />
        <p className="text-sm font-semibold text-foreground">Cargando el checkout seguro de Wompi...</p>
        <p className="text-xs leading-5 text-muted-foreground">Se están preparando los elementos de pago cifrados (PCI DSS).</p>
      </div>
    )
  }

  if (scriptState === 'error') {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 rounded-xl border border-negative/30 bg-negative/10 px-6 py-10 text-center">
        <p className="text-sm font-semibold text-negative">{scriptError ?? 'No se pudo cargar el checkout seguro de Wompi.'}</p>
        <button type="button" onClick={() => setBootAttempt((value) => value + 1)} className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border bg-surface px-4 text-xs font-semibold text-foreground transition-colors hover:bg-surface-raised">
          Reintentar
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start gap-3 rounded-xl border border-positive/20 bg-positive/5 p-3 text-xs text-muted-foreground">
        <LockKeyhole className="mt-0.5 size-4 shrink-0 text-positive" aria-hidden="true" />
        <p>Los datos de tu tarjeta se capturan en los elementos seguros de Wompi (PCI DSS). BetMind no ve ni guarda el número ni el código de tu tarjeta.</p>
      </div>

      <div className="flex flex-col items-center gap-4 rounded-xl border border-brand/25 bg-brand/5 px-6 py-10 text-center">
        <div className="flex size-12 items-center justify-center rounded-2xl border border-brand/30 bg-brand/10 text-brand"><CreditCard className="size-6" aria-hidden="true" /></div>
        <div>
          <p className="text-sm font-semibold text-foreground">Checkout seguro de Wompi</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">Se abrirá el formulario cifrado de Wompi para completar la tokenización de tu tarjeta.</p>
        </div>
        <button type="button" onClick={openWompiCheckout} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-brand px-4 text-sm font-bold text-primary-foreground transition-[transform,opacity] duration-150 hover:opacity-90 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand">
          <LockKeyhole className="size-4" aria-hidden="true" /> Continuar con esta tarjeta
        </button>
      </div>

      <p className="text-xs leading-5 text-subtle">Al tokenizar tu tarjeta, el plan {plan === 'anual' ? 'anual (COP 249.900)' : 'mensual (COP 29.900)'} quedará en estado PENDING hasta que Wompi confirme la operación.</p>
    </div>
  )
}
