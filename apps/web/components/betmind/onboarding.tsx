'use client'

import * as React from 'react'
import { ArrowLeft, ArrowRight, Check, ShieldCheck, Sparkles, Target } from 'lucide-react'

import { cn } from '@/lib/utils'

const ONBOARDING_KEY = 'betmind_onboarding_seen'

function SignalPreview() {
  return (
    <div className="relative mx-auto w-full max-w-sm rounded-2xl border border-border bg-card p-4 shadow-2xl shadow-primary/10">
      <div className="absolute -right-5 -top-5 flex size-14 items-center justify-center rounded-2xl border border-positive/30 bg-positive/10 text-positive shadow-lg">
        <Sparkles size={22} aria-hidden="true" />
      </div>
      <div className="flex items-center justify-between border-b border-border/60 pb-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-subtle">Señal detectada</p>
          <p className="mt-1 text-base font-semibold text-foreground">EDGE · +EV</p>
        </div>
        <span className="rounded-full border border-positive/30 bg-positive/10 px-2.5 py-1 font-mono text-xs font-bold text-positive">+12.4%</span>
      </div>
      <div className="space-y-3 py-4">
        <div className="flex items-center justify-between rounded-xl bg-surface-raised px-3 py-2.5">
          <span className="text-sm text-foreground">Local gana</span>
          <span className="font-mono text-sm font-bold text-foreground">2.10</span>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-[10px] uppercase tracking-wider text-subtle">
          <span className="rounded-lg border border-border/60 px-2 py-2">xG 1.82</span>
          <span className="rounded-lg border border-border/60 px-2 py-2">74% confianza</span>
          <span className="rounded-lg border border-border/60 px-2 py-2">Kelly 2.1%</span>
        </div>
      </div>
      <div className="flex items-center gap-2 border-t border-border/60 pt-3 text-xs text-muted-foreground">
        <ShieldCheck size={14} className="text-positive" aria-hidden="true" />
        Modelo calibrado con datos recientes
      </div>
    </div>
  )
}

function SignalGlossary() {
  const [active, setActive] = React.useState<'ev' | 'xg' | 'kelly'>('ev')
  const items = {
    ev: {
      label: 'EV',
      value: '+10%',
      title: 'Valor Esperado',
      text: 'Cuánto más (o menos) pagaría esta cuota si nuestro modelo tiene razón. +10% EV significa que, en promedio, esta apuesta rinde 10% más de lo que la cuota sugiere.',
    },
    xg: {
      label: 'xG',
      value: '1.82',
      title: 'Goles Esperados',
      text: 'Cuántos goles debería anotar cada equipo según su rendimiento reciente, más allá del resultado final.',
    },
    kelly: {
      label: 'Confianza / Kelly',
      value: '2.1%',
      title: 'Tamaño sugerido',
      text: 'Cuánto de tu bankroll arriesgar en esta selección, calculado para maximizar tu crecimiento sin exponerte a una mala racha.',
    },
  } as const
  const selected = items[active]

  return (
    <div className="w-full max-w-md rounded-2xl border border-border bg-card p-4 shadow-xl shadow-primary/5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-subtle">Ejemplo en vivo</p>
          <p className="mt-1 font-semibold text-foreground">Atlético Norte vs. Central</p>
        </div>
        <span className="rounded-md bg-positive/10 px-2 py-1 font-mono text-xs font-bold text-positive">+EV</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {(Object.keys(items) as Array<keyof typeof items>).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setActive(key)}
            className={cn(
              'rounded-xl border px-2 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
              active === key ? 'border-primary/50 bg-primary/10' : 'border-border/60 bg-surface/40 hover:bg-surface-raised',
            )}
          >
            <span className="block text-[10px] font-semibold uppercase tracking-wider text-subtle">{items[key].label}</span>
            <span className="mt-1 block font-mono text-base font-bold text-foreground">{items[key].value}</span>
          </button>
        ))}
      </div>
      <div className="mt-4 rounded-xl border border-border/60 bg-surface-inset p-3" aria-live="polite">
        <p className="text-xs font-semibold text-foreground">{selected.title}</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{selected.text}</p>
      </div>
    </div>
  )
}

function OnboardingSlide({ children, eyebrow, title, subtitle }: { children: React.ReactNode; eyebrow: string; title: string; subtitle: string }) {
  return (
    <section className="flex min-h-[29rem] flex-col justify-center gap-8" aria-label={title}>
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-primary">{eyebrow}</p>
        <h1 className="max-w-xl text-3xl font-bold tracking-tight text-foreground sm:text-5xl">{title}</h1>
        <p className="mt-4 max-w-xl text-base leading-7 text-muted-foreground">{subtitle}</p>
      </div>
      <div>{children}</div>
    </section>
  )
}

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [activeSlide, setActiveSlide] = React.useState(0)
  const touchStart = React.useRef<number | null>(null)

  function goToSlide(index: number) {
    setActiveSlide(Math.max(0, Math.min(2, index)))
  }

  function complete() {
    window.localStorage.setItem(ONBOARDING_KEY, 'true')
    onComplete()
  }

  return (
    <main className="min-h-svh bg-background px-4 py-6 sm:px-8 lg:px-12">
      <div className="mx-auto flex min-h-[calc(100svh-3rem)] w-full max-w-6xl flex-col">
        <header className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg border border-positive/40 bg-positive/10 font-mono text-xs font-bold text-positive">BM</div>
          <div>
            <p className="text-sm font-semibold text-foreground">BetMind AI</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-subtle">Análisis deportivo</p>
          </div>
          <span className="ml-auto text-xs text-subtle">{activeSlide + 1} / 3</span>
        </header>

        <div
          className="flex flex-1 items-center"
          onTouchStart={(event) => { touchStart.current = event.changedTouches[0]?.clientX ?? null }}
          onTouchEnd={(event) => {
            const start = touchStart.current
            const end = event.changedTouches[0]?.clientX
            touchStart.current = null
            if (start === null || end === undefined || Math.abs(end - start) < 48) return
            goToSlide(activeSlide + (end < start ? 1 : -1))
          }}
        >
          <div className="grid w-full grid-cols-1 gap-8 lg:grid-cols-[1fr_auto] lg:items-center">
            <div className="min-w-0">
              {activeSlide === 0 && (
                <OnboardingSlide
                  eyebrow="Bienvenido a BetMind"
                  title="Tu analista cuantitativo, no tu suerte."
                  subtitle="BetMind analiza cada partido con el mismo modelo estadístico que usan las casas de apuestas — para que apuestes con la misma información que ellas, no menos."
                >
                  <SignalPreview />
                </OnboardingSlide>
              )}
              {activeSlide === 1 && (
                <OnboardingSlide
                  eyebrow="Cómo funciona"
                  title="Así leemos una señal +EV"
                  subtitle="Tocá cada indicador para entender qué está midiendo el modelo antes de explorar tus propias señales."
                >
                  {/* Datos de ejemplo fijos para onboarding, no vienen de la API */}
                  <SignalGlossary />
                </OnboardingSlide>
              )}
              {activeSlide === 2 && (
                <OnboardingSlide
                  eyebrow="Listo para empezar"
                  title="Empezá a explorar, sin registrarte"
                  subtitle="Guardá boletos y seguí tu historial desde ya. Podés crear una cuenta más adelante para no perder tu progreso."
                >
                  <div className="max-w-md rounded-2xl border border-border bg-card p-5">
                    <div className="flex items-start gap-3">
                      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"><Target size={17} aria-hidden="true" /></div>
                      <div>
                        <p className="font-semibold text-foreground">Tu espacio de análisis está listo</p>
                        <p className="mt-1 text-sm leading-6 text-muted-foreground">Empezá en modo anónimo y guardá tus primeros boletos en este dispositivo.</p>
                      </div>
                    </div>
                  </div>
                  {/* TODO(auth): cuando exista registro real, agregar paso de creación de cuenta acá */}
                </OnboardingSlide>
              )}
            </div>

            <div className="hidden items-center justify-center lg:flex" aria-hidden="true">
              <div className="flex flex-col gap-3">
                {[0, 1, 2].map((index) => <span key={index} className={cn('size-2 rounded-full transition-colors', index === activeSlide ? 'bg-primary' : 'bg-border')} />)}
              </div>
            </div>
          </div>
        </div>

        <footer className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center justify-center gap-2 sm:justify-start" role="tablist" aria-label="Pantallas de bienvenida">
            {[0, 1, 2].map((index) => (
              <button
                key={index}
                type="button"
                role="tab"
                aria-selected={activeSlide === index}
                aria-label={`Ir a pantalla ${index + 1}`}
                onClick={() => goToSlide(index)}
                className={cn('h-2 rounded-full transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary', activeSlide === index ? 'w-8 bg-primary' : 'w-2 bg-border hover:bg-subtle')}
              />
            ))}
          </div>
          <div className="flex items-center justify-between gap-3 sm:justify-end">
            <button type="button" onClick={() => goToSlide(activeSlide - 1)} disabled={activeSlide === 0} className="inline-flex size-11 items-center justify-center rounded-xl border border-border text-muted-foreground transition-colors hover:bg-surface-raised hover:text-foreground disabled:pointer-events-none disabled:opacity-30" aria-label="Pantalla anterior">
              <ArrowLeft size={17} aria-hidden="true" />
            </button>
            {activeSlide < 2 ? (
              <button type="button" onClick={() => goToSlide(activeSlide + 1)} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                Continuar <ArrowRight size={16} aria-hidden="true" />
              </button>
            ) : (
              <button type="button" onClick={complete} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-6 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                <Check size={16} aria-hidden="true" />
                Empezar
              </button>
            )}
          </div>
        </footer>
      </div>
    </main>
  )
}

export function OnboardingGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = React.useState(false)
  const [seen, setSeen] = React.useState(false)

  React.useEffect(() => {
    setSeen(window.localStorage.getItem(ONBOARDING_KEY) === 'true')
    setReady(true)
  }, [])

  if (!ready) return null
  if (!seen) return <Onboarding onComplete={() => setSeen(true)} />
  return <>{children}</>
}
