'use client'

import * as React from 'react'
import Link from 'next/link'
import {
  ArrowDownRight,
  ArrowUpRight,
  CircleDollarSign,
  Shield,
  Ticket,
  TrendingUp,
  Wallet,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  adjustBankroll,
  setupBankroll,
  updateRiskProfile,
  type Bankroll,
  type BankrollMovement,
  type RiskProfile,
} from '@/lib/bankroll'
import { formatCOP, formatCOPInput, formatCOTDate, parseCOPInput } from '@/lib/formatters'
import { cn } from '@/lib/utils'

import { AppShell } from './app-shell'
import { useBankroll } from './use-bankroll'
import { useProStatus } from './use-pro-status'

const PROFILE_OPTIONS: Array<{
  value: RiskProfile
  label: string
  detail: string
  Icon: LucideIcon
}> = [
  { value: 'conservador', label: 'Conservador', detail: 'Quarter-Kelly', Icon: Shield },
  { value: 'moderado', label: 'Moderado', detail: 'Half-Kelly', Icon: TrendingUp },
  { value: 'agresivo', label: 'Agresivo', detail: 'Full-Kelly', Icon: Zap },
]

const COT_DATE_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  timeZone: 'America/Bogota',
})

function isSameCOTDay(left: string, right: string): boolean {
  return COT_DATE_FORMATTER.format(new Date(left)) === COT_DATE_FORMATTER.format(new Date(right))
}

function Paywall() {
  return (
    <div className="mx-auto flex min-h-[68vh] max-w-2xl items-center justify-center">
      <section className="w-full rounded-3xl border border-brand/25 bg-card p-7 text-center shadow-2xl shadow-brand/5 sm:p-10">
        <div className="mx-auto flex size-14 items-center justify-center rounded-2xl border border-brand/30 bg-brand/10 text-brand">
          <Wallet size={24} aria-hidden="true" />
        </div>
        <p className="mt-6 text-xs font-semibold uppercase tracking-[0.24em] text-brand">BetMind PRO</p>
        <h1 className="mt-3 font-serif text-3xl leading-tight tracking-tight text-foreground sm:text-5xl">Gestioná tu bankroll real con PRO</h1>
        <p className="mx-auto mt-4 max-w-lg text-sm leading-7 text-muted-foreground">Convertí el % de Kelly en pesos exactos, seguí la evolución de tu capital y elegí tu perfil de riesgo. 7 días gratis.</p>
        <Link href="/planes" className="mt-7 inline-flex min-h-11 items-center justify-center rounded-xl bg-brand px-5 text-sm font-bold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand">Probar PRO gratis →</Link>
      </section>
    </div>
  )
}

function SetupFlow({ onCreated }: { onCreated: (bankroll: Bankroll) => void }) {
  const [step, setStep] = React.useState<1 | 2>(1)
  const [capitalInput, setCapitalInput] = React.useState('')
  const [profile, setProfile] = React.useState<RiskProfile>('moderado')
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  const capital = parseCOPInput(capitalInput)

  function continueToProfile() {
    if (capital == null || capital <= 0) {
      setError('Ingresá un monto mayor a $0.')
      return
    }
    setError(null)
    setStep(2)
  }

  async function submit() {
    if (capital == null || capital <= 0) {
      setStep(1)
      setError('Ingresá un monto mayor a $0.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      onCreated(await setupBankroll(capital, profile))
    } catch (setupError) {
      setError(setupError instanceof Error ? setupError.message : 'No se pudo configurar tu bankroll.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="mx-auto w-full max-w-3xl rounded-3xl border border-border bg-card p-6 sm:p-9">
      <div className="flex items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div>
          <p className="terminal-kicker text-primary">Configuración inicial</p>
          <p className="mt-2 text-sm text-muted-foreground">Dos decisiones para que el ledger refleje tu realidad.</p>
        </div>
        <span className="font-mono text-xs tabular-nums text-subtle">0{step} / 02</span>
      </div>

      {step === 1 ? (
        <div className="pt-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Capital base</p>
          <h1 className="mt-3 font-serif text-3xl tracking-tight text-foreground sm:text-5xl">¿Cuánto vas a gestionar?</h1>
          <p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">Usaremos este monto para traducir cada sugerencia Kelly a una cifra concreta. Podés ajustarlo más adelante.</p>
          <label className="mt-8 block text-xs font-semibold text-foreground">
            Capital inicial en COP
            <div className="mt-2 flex items-center rounded-xl border border-border bg-surface px-4 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
              <span className="font-mono text-lg text-muted-foreground">$</span>
              <input
                autoFocus
                inputMode="numeric"
                value={capitalInput}
                onChange={(event) => {
                  const raw = event.target.value
                  const parsed = parseCOPInput(raw)
                  setCapitalInput(parsed == null ? (raw.includes('-') ? '-' : '') : formatCOPInput(parsed))
                  setError(null)
                }}
                placeholder="500.000"
                className="min-h-14 w-full bg-transparent px-3 text-right font-mono text-3xl font-bold tabular-nums text-foreground outline-none placeholder:text-muted-foreground/40"
                aria-label="Capital inicial en pesos colombianos"
              />
            </div>
          </label>
          {error && <InlineError message={error} />}
          <Button type="button" className="mt-7 min-h-11 w-full" onClick={continueToProfile}>Continuar</Button>
        </div>
      ) : (
        <div className="pt-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Perfil de riesgo</p>
          <h1 className="mt-3 font-serif text-3xl tracking-tight text-foreground sm:text-5xl">¿Qué tan agresivo querés ser?</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">Esto define la fracción de Kelly que usarás como referencia para cada boleto.</p>
          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            {PROFILE_OPTIONS.map(({ value, label, detail, Icon }) => {
              const active = profile === value
              return (
                <button key={value} type="button" aria-pressed={active} onClick={() => setProfile(value)} className={cn('flex min-h-32 flex-col items-start justify-between rounded-2xl border p-4 text-left transition-[border-color,background-color,transform] duration-200 ease-out active:scale-[0.98]', active ? 'border-primary/70 bg-primary/10 text-primary' : 'border-border bg-surface/40 text-muted-foreground hover:-translate-y-0.5 hover:border-primary/35 hover:bg-surface')}>
                  <Icon size={21} aria-hidden="true" />
                  <span><span className="block text-sm font-bold text-foreground">{label}</span><span className="mt-1 block font-mono text-[10px] uppercase tracking-wider">{detail}</span></span>
                </button>
              )
            })}
          </div>
          {profile === 'agresivo' && <p className="mt-4 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-xs leading-5 text-warning">Full-Kelly maximiza el crecimiento pero también la volatilidad — podés perder más del 50% de tu bankroll en una mala racha.</p>}
          {error && <InlineError message={error} />}
          <div className="mt-7 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
            <Button type="button" variant="outline" onClick={() => { setError(null); setStep(1) }} disabled={saving}>Atrás</Button>
            <Button type="button" onClick={() => void submit()} disabled={saving}>{saving ? 'Configurando…' : 'Empezar a gestionar mi bankroll'}</Button>
          </div>
        </div>
      )}
    </section>
  )
}

function InlineError({ message }: { message: string }) {
  return <p role="alert" className="mt-4 rounded-xl border border-negative/30 bg-negative/10 px-4 py-3 text-xs leading-5 text-negative">{message}</p>
}

function EvolutionChart({ points }: { points: Array<{ date: string; capital: number }> }) {
  const width = 760
  const height = 260
  const padding = { top: 20, right: 18, bottom: 38, left: 72 }
  const values = points.map((point) => point.capital)
  const minimum = Math.min(0, ...values)
  const maximum = Math.max(1, ...values)
  const range = Math.max(1, maximum - minimum)
  const x = (index: number) => padding.left + (index / Math.max(1, points.length - 1)) * (width - padding.left - padding.right)
  const y = (value: number) => padding.top + (1 - (value - minimum) / range) * (height - padding.top - padding.bottom)
  const coordinates = points.map((point, index) => `${x(index)},${y(point.capital)}`).join(' ')
  const area = `${padding.left},${height - padding.bottom} ${coordinates} ${x(points.length - 1)},${height - padding.bottom}`

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface/45 p-3 sm:p-5">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label="Evolución acumulada del capital">
        <line x1={padding.left} y1={y(0)} x2={width - padding.right} y2={y(0)} stroke="var(--border)" strokeDasharray="4 5" />
        <text x={padding.left - 10} y={padding.top + 4} textAnchor="end" fill="var(--subtle)" fontSize="11">{formatCOP(maximum)}</text>
        <text x={padding.left - 10} y={height - padding.bottom + 4} textAnchor="end" fill="var(--subtle)" fontSize="11">{formatCOP(minimum)}</text>
        <polygon points={area} fill="var(--primary)" opacity="0.08" />
        <polyline points={coordinates} fill="none" stroke="var(--primary)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((point, index) => <circle key={`${point.date}-${index}`} cx={x(index)} cy={y(point.capital)} r="4" fill="var(--surface)" stroke="var(--primary)" strokeWidth="2"><title>{`${formatCOTDate(point.date)} · ${formatCOP(point.capital)}`}</title></circle>)}
        {points.length > 1 && <text x={padding.left} y={height - 10} fill="var(--subtle)" fontSize="10">{formatCOTDate(points[0].date)}</text>}
        {points.length > 1 && <text x={width - padding.right} y={height - 10} textAnchor="end" fill="var(--subtle)" fontSize="10">{formatCOTDate(points[points.length - 1].date)}</text>}
      </svg>
    </div>
  )
}

function movementLabel(movement: BankrollMovement, initialMovementId: string | null): string {
  if (movement.id === initialMovementId) return 'Capital inicial'
  if (movement.type === 'ticket_won') return 'Boleto ganado'
  if (movement.type === 'ticket_lost') return 'Boleto perdido'
  if (movement.type === 'ticket_void') return 'Boleto anulado'
  return 'Ajuste manual'
}

function MovementIcon({ movement }: { movement: BankrollMovement }) {
  if (movement.amount > 0) return <ArrowUpRight size={17} aria-hidden="true" />
  if (movement.amount < 0) return <ArrowDownRight size={17} aria-hidden="true" />
  return <CircleDollarSign size={17} aria-hidden="true" />
}

function Dashboard({ bankroll, onChange }: { bankroll: Bankroll; onChange: (bankroll: Bankroll) => void }) {
  const [adjustOpen, setAdjustOpen] = React.useState(false)
  const [riskSaving, setRiskSaving] = React.useState(false)
  const [adjustAmount, setAdjustAmount] = React.useState('')
  const [reason, setReason] = React.useState('')
  const [adjustError, setAdjustError] = React.useState<string | null>(null)
  const [adjustSaving, setAdjustSaving] = React.useState(false)

  const chronological = React.useMemo(
    () => [...bankroll.movements].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    [bankroll.movements],
  )
  const recent = React.useMemo(() => [...chronological].reverse(), [chronological])
  const points = React.useMemo(() => {
    const firstDate = bankroll.created_at ?? chronological[0]?.created_at ?? new Date().toISOString()
    let running = 0
    const next = [{ date: firstDate, capital: 0 }]
    chronological.forEach((movement) => {
      running += movement.amount
      next.push({ date: movement.created_at, capital: running })
    })
    return next
  }, [bankroll.created_at, chronological])
  const initialMovementId = chronological[0] && chronological[0].type === 'manual_adjustment' && isSameCOTDay(chronological[0].created_at, bankroll.created_at)
    ? chronological[0].id
    : null
  const monthVariation = React.useMemo(() => {
    const now = new Date()
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    return bankroll.movements
      .filter((movement) => new Date(movement.created_at) >= monthStart)
      .reduce((total, movement) => total + movement.amount, 0)
  }, [bankroll.movements])

  async function handleRiskChange(value: RiskProfile) {
    if (value === bankroll.risk_profile) return
    setRiskSaving(true)
    try {
      onChange(await updateRiskProfile(value))
    } catch (riskError) {
      toast.error(riskError instanceof Error ? riskError.message : 'No se pudo actualizar el perfil.')
    } finally {
      setRiskSaving(false)
    }
  }

  async function handleAdjust(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const amount = parseCOPInput(adjustAmount)
    if (amount == null) {
      setAdjustError('Ingresá un monto válido.')
      return
    }
    if (!reason.trim()) {
      setAdjustError('Escribí un motivo para este movimiento.')
      return
    }
    setAdjustSaving(true)
    setAdjustError(null)
    try {
      onChange(await adjustBankroll(amount, reason.trim()))
      setAdjustOpen(false)
      setAdjustAmount('')
      setReason('')
      toast.success('Capital actualizado')
    } catch (adjustmentError) {
      setAdjustError(adjustmentError instanceof Error ? adjustmentError.message : 'No se pudo ajustar el capital.')
    } finally {
      setAdjustSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-5 rounded-3xl border border-border bg-card p-6 sm:flex-row sm:items-end sm:justify-between sm:p-8">
        <div>
          <p className="terminal-kicker text-primary">Ledger de capital</p>
          <h1 className="mt-3 font-serif text-4xl tracking-tight text-foreground sm:text-6xl">{formatCOP(bankroll.current_capital)}</h1>
          <p className={cn('mt-3 flex items-center gap-1.5 text-sm font-semibold', monthVariation > 0 ? 'text-positive' : monthVariation < 0 ? 'text-negative' : 'text-muted-foreground')}>
            {monthVariation > 0 ? <ArrowUpRight size={16} aria-hidden="true" /> : monthVariation < 0 ? <ArrowDownRight size={16} aria-hidden="true" /> : null}
            {monthVariation === 0 ? 'Sin variación este mes' : `${monthVariation > 0 ? '+' : ''}${formatCOP(monthVariation)} este mes`}
          </p>
        </div>
        <Button type="button" variant="outline" onClick={() => { setAdjustError(null); setAdjustOpen(true) }}><Wallet data-icon="inline-start" aria-hidden="true" /> Ajustar capital</Button>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,0.6fr)]">
        <section className="rounded-2xl border border-border bg-card p-5 sm:p-6" aria-labelledby="evolution-title">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div><p className="terminal-kicker">Evolución</p><h2 id="evolution-title" className="mt-2 text-lg font-semibold text-foreground">Capital acumulado</h2></div>
            <span className="text-xs text-subtle">Desde la configuración</span>
          </div>
          <div className="mt-5"><EvolutionChart points={points} /></div>
        </section>

        <section className="rounded-2xl border border-border bg-card p-5 sm:p-6" aria-labelledby="risk-title">
          <div><p className="terminal-kicker">Control de riesgo</p><h2 id="risk-title" className="mt-2 text-lg font-semibold text-foreground">Perfil actual</h2></div>
          <div className="mt-5 flex flex-col gap-2">
            {PROFILE_OPTIONS.map(({ value, label, detail, Icon }) => (
              <button key={value} type="button" disabled={riskSaving} onClick={() => void handleRiskChange(value)} className={cn('flex items-center gap-3 rounded-xl border px-3 py-3 text-left transition-[border-color,background-color,transform] duration-200 ease-out active:scale-[0.98]', bankroll.risk_profile === value ? 'border-primary/60 bg-primary/10' : 'border-border bg-surface/35 hover:border-primary/30 hover:bg-surface')}>
                <span className={cn('flex size-9 items-center justify-center rounded-lg', bankroll.risk_profile === value ? 'bg-primary/15 text-primary' : 'bg-surface-raised text-muted-foreground')}><Icon size={17} aria-hidden="true" /></span>
                <span className="min-w-0"><span className="block text-sm font-semibold text-foreground">{label}</span><span className="font-mono text-[10px] uppercase tracking-wider text-subtle">{detail}</span></span>
                {bankroll.risk_profile === value && <span className="ml-auto size-2 rounded-full bg-primary" aria-label="Perfil seleccionado" />}
              </button>
            ))}
          </div>
          {bankroll.risk_profile === 'agresivo' && <p className="mt-4 text-xs leading-5 text-warning">Full-Kelly maximiza el crecimiento y también la volatilidad.</p>}
        </section>
      </div>

      <section className="rounded-2xl border border-border bg-card" aria-labelledby="movements-title">
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border/60 p-5 sm:p-6"><div><p className="terminal-kicker">Actividad</p><h2 id="movements-title" className="mt-2 text-lg font-semibold text-foreground">Movimientos</h2></div><span className="font-mono text-xs text-subtle">{recent.length} registros</span></div>
        {recent.length ? <ul className="divide-y divide-border/50">{recent.map((movement) => {
          const positive = movement.amount > 0
          return <li key={movement.id} className="flex items-center gap-3 px-5 py-4 sm:px-6"><span className={cn('flex size-9 shrink-0 items-center justify-center rounded-xl', positive ? 'bg-positive/10 text-positive' : movement.amount < 0 ? 'bg-negative/10 text-negative' : 'bg-surface-raised text-muted-foreground')}><MovementIcon movement={movement} /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-foreground">{movementLabel(movement, initialMovementId)}</p><p className="mt-1 truncate text-xs text-subtle">{formatCOTDate(movement.created_at)}{movement.reason ? ` · ${movement.reason}` : ''}</p></div>{movement.ticket_id ? <Link href={`/historial?ticket=${movement.ticket_id}`} className="hidden items-center gap-1 text-xs font-semibold text-primary hover:underline sm:inline-flex"><Ticket size={13} aria-hidden="true" /> Boleto #{movement.ticket_id}</Link> : null}<span className={cn('shrink-0 font-mono text-sm font-bold tabular-nums', positive ? 'text-positive' : movement.amount < 0 ? 'text-negative' : 'text-muted-foreground')}>{movement.amount > 0 ? '+' : ''}{formatCOP(movement.amount)}</span></li>
        })}</ul> : <p className="p-8 text-center text-sm text-muted-foreground">Todavía no hay movimientos.</p>}
      </section>

      <Dialog open={adjustOpen} onOpenChange={setAdjustOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Ajustar capital</DialogTitle><DialogDescription>Registrá un depósito o retiro manual. El movimiento quedará en tu historial.</DialogDescription></DialogHeader>
          <form onSubmit={(event) => void handleAdjust(event)} className="flex flex-col gap-4">
            <label className="text-xs font-semibold text-foreground">Monto en COP<input inputMode="numeric" value={adjustAmount} onChange={(event) => { const raw = event.target.value; const parsed = parseCOPInput(raw); setAdjustAmount(parsed == null ? (raw.includes('-') ? '-' : '') : formatCOPInput(parsed)); setAdjustError(null) }} placeholder="-100.000 o 500.000" className="mt-2 min-h-11 w-full rounded-lg border border-border bg-surface px-3 text-right font-mono text-lg font-bold tabular-nums text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" /></label>
            <label className="text-xs font-semibold text-foreground">Motivo<textarea value={reason} onChange={(event) => { setReason(event.target.value); setAdjustError(null) }} maxLength={500} rows={3} placeholder="Ej. Depósito de quincena" className="mt-2 w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" /></label>
            {adjustError && <InlineError message={adjustError} />}
            <DialogFooter><Button type="button" variant="outline" onClick={() => setAdjustOpen(false)} disabled={adjustSaving}>Cancelar</Button><Button type="submit" disabled={adjustSaving}>{adjustSaving ? 'Guardando…' : 'Guardar ajuste'}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export function BankrollPage() {
  const isPro = useProStatus()
  const { bankroll, setBankroll, loading, error, reload } = useBankroll(isPro)

  return (
    <AppShell>
      {!isPro ? <Paywall /> : loading ? <div aria-busy="true" className="h-[65vh] rounded-3xl border border-border bg-card skeleton" /> : error ? <div className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center text-center"><p className="text-sm font-semibold text-foreground">No pudimos cargar tu bankroll</p><p className="mt-2 text-xs text-muted-foreground">{error}</p><Button type="button" variant="outline" className="mt-5" onClick={() => void reload()}>Reintentar</Button></div> : bankroll ? <Dashboard bankroll={bankroll} onChange={setBankroll} /> : <SetupFlow onCreated={setBankroll} />}
    </AppShell>
  )
}
