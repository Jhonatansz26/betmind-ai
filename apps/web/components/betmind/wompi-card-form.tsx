'use client'

import * as React from 'react'
import { ExternalLink, LockKeyhole, ShieldCheck } from 'lucide-react'

import {
  fetchWompiAcceptance,
  tokenizeCard,
  type CardDetails,
  type WompiMerchantAcceptance,
  type WompiCardToken,
} from '@/lib/wompi'

interface WompiCardFormProps {
  onTokenized: (result: WompiCardToken) => void
  disabled?: boolean
}

const inputClassName = 'min-h-11 w-full rounded-xl border border-border bg-surface/40 px-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] placeholder:text-muted-foreground/60 focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60'

export function WompiCardForm({ onTokenized, disabled = false }: WompiCardFormProps) {
  const [acceptance, setAcceptance] = React.useState<WompiMerchantAcceptance | null>(null)
  const [termsAccepted, setTermsAccepted] = React.useState(false)
  const [privacyAccepted, setPrivacyAccepted] = React.useState(false)
  const [number, setNumber] = React.useState('')
  const [month, setMonth] = React.useState('')
  const [year, setYear] = React.useState('')
  const [cvc, setCvc] = React.useState('')
  const [cardHolder, setCardHolder] = React.useState('')
  const [loadingAcceptance, setLoadingAcceptance] = React.useState(true)
  const [tokenizing, setTokenizing] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let active = true
    void fetchWompiAcceptance()
      .then((data) => {
        if (active) setAcceptance(data)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'No se pudieron cargar los contratos de Wompi.')
      })
      .finally(() => {
        if (active) setLoadingAcceptance(false)
      })
    return () => {
      active = false
    }
  }, [])

  function clearCardFields() {
    setNumber('')
    setMonth('')
    setYear('')
    setCvc('')
    setCardHolder('')
    setTermsAccepted(false)
    setPrivacyAccepted(false)
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    if (!acceptance || !termsAccepted || !privacyAccepted) return
    setTokenizing(true)

    const card: CardDetails = {
      number: number.replace(/\s/g, ''),
      exp_month: month.padStart(2, '0'),
      exp_year: year.slice(-2),
      cvc,
      card_holder: cardHolder.trim(),
    }

    try {
      const result = await tokenizeCard(card, acceptance)
      clearCardFields()
      onTokenized(result)
    } catch (reason: unknown) {
      clearCardFields()
      setError(reason instanceof Error ? reason.message : 'Wompi no pudo tokenizar esta tarjeta.')
    } finally {
      setTokenizing(false)
    }
  }

  const formDisabled = disabled || tokenizing || loadingAcceptance || !acceptance

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div className="flex items-start gap-3 rounded-xl border border-positive/20 bg-positive/5 p-3 text-xs text-muted-foreground">
        <LockKeyhole className="mt-0.5 size-4 shrink-0 text-positive" aria-hidden="true" />
        <p>Los datos se cifran en tu navegador y se envían directamente a Wompi. BetMind no guarda el número ni el código de tu tarjeta.</p>
      </div>

      <div className="grid gap-4">
        <label className="flex flex-col gap-1.5 text-xs font-semibold text-foreground">
          Número de tarjeta
          <input className={inputClassName} inputMode="numeric" autoComplete="cc-number" maxLength={23} value={number} onChange={(event) => setNumber(event.target.value)} placeholder="4242 4242 4242 4242" disabled={formDisabled} required />
        </label>
        <label className="flex flex-col gap-1.5 text-xs font-semibold text-foreground">
          Nombre del titular
          <input className={inputClassName} autoComplete="cc-name" value={cardHolder} onChange={(event) => setCardHolder(event.target.value)} placeholder="Como aparece en la tarjeta" disabled={formDisabled} required />
        </label>
        <div className="grid grid-cols-3 gap-3">
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-foreground">
            Mes
            <input className={inputClassName} inputMode="numeric" autoComplete="cc-exp-month" maxLength={2} value={month} onChange={(event) => setMonth(event.target.value.replace(/\D/g, '').slice(0, 2))} placeholder="MM" disabled={formDisabled} required />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-foreground">
            Año
            <input className={inputClassName} inputMode="numeric" autoComplete="cc-exp-year" maxLength={2} value={year} onChange={(event) => setYear(event.target.value.replace(/\D/g, '').slice(0, 2))} placeholder="AA" disabled={formDisabled} required />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-foreground">
            CVC
            <input className={inputClassName} inputMode="numeric" autoComplete="cc-csc" maxLength={4} value={cvc} onChange={(event) => setCvc(event.target.value.replace(/\D/g, '').slice(0, 4))} placeholder="123" disabled={formDisabled} required />
          </label>
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface/30 p-4">
        <p className="flex items-center gap-2 text-xs font-semibold text-foreground"><ShieldCheck className="size-4 text-brand" aria-hidden="true" />Aceptaciones obligatorias</p>
        {acceptance ? (
          <>
            <label className="flex cursor-pointer items-start gap-3 text-xs leading-5 text-muted-foreground">
              <input type="checkbox" className="mt-1 size-4 shrink-0 accent-brand" checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} disabled={formDisabled} />
              <span>Acepto la <a className="font-semibold text-brand underline underline-offset-2" href={acceptance.presigned_acceptance.permalink} target="_blank" rel="noreferrer">política y condiciones de uso <ExternalLink className="inline size-3" aria-hidden="true" /></a> de Wompi.</span>
            </label>
            <label className="flex cursor-pointer items-start gap-3 text-xs leading-5 text-muted-foreground">
              <input type="checkbox" className="mt-1 size-4 shrink-0 accent-brand" checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} disabled={formDisabled} />
              <span>Autorizo el tratamiento de mis <a className="font-semibold text-brand underline underline-offset-2" href={acceptance.presigned_personal_data_auth.permalink} target="_blank" rel="noreferrer">datos personales <ExternalLink className="inline size-3" aria-hidden="true" /></a>.</span>
            </label>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">Cargando los contratos vigentes de Wompi...</p>
        )}
      </div>

      {error && <p role="alert" className="rounded-lg border border-negative/30 bg-negative/10 px-3 py-2 text-xs font-medium text-negative">{error}</p>}
      <button type="submit" disabled={formDisabled || !termsAccepted || !privacyAccepted} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-brand px-4 text-sm font-bold text-primary-foreground transition-[transform,opacity] duration-150 hover:opacity-90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50">
        {tokenizing ? 'Cifrando y tokenizando...' : loadingAcceptance ? 'Cargando contratos...' : 'Continuar con esta tarjeta'}
      </button>
    </form>
  )
}
