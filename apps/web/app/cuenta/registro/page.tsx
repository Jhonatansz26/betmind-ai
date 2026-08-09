'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

import { register } from '@/lib/auth'
import { claimPendingTickets } from '@/components/betmind/tracking-panel'

export default function RegistroPage() {
  const router = useRouter()
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [fullName, setFullName] = React.useState('')
  const [ageConfirmed, setAgeConfirmed] = React.useState(false)
  const [ageError, setAgeError] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setAgeError(false)

    if (!ageConfirmed) {
      setAgeError(true)
      return
    }
    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.')
      return
    }

    setLoading(true)
    try {
      await register(email, password, fullName || undefined)
      // Task 5: claim anonymous tickets silently
      claimPendingTickets().catch((err: unknown) => console.error('[claim]', err))
      router.push('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ocurrió un error inesperado.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-sm">
      <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Crear cuenta gratis</h1>
        <p className="mb-6 text-sm text-muted-foreground">
          ¿Ya tenés cuenta?{' '}
          <Link href="/cuenta/login" className="font-semibold text-primary hover:underline">
            Iniciar sesión
          </Link>
        </p>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-negative/30 bg-negative/10 px-4 py-3 text-sm font-medium text-negative"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="registro-nombre" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Nombre <span className="font-normal normal-case text-muted-foreground/60">(opcional)</span>
            </label>
            <input
              id="registro-nombre"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="rounded-lg border border-border bg-surface/40 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              placeholder="Tu nombre"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="registro-email" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Email
            </label>
            <input
              id="registro-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-lg border border-border bg-surface/40 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              placeholder="tu@email.com"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="registro-password" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Contraseña <span className="font-normal normal-case text-muted-foreground/60">(mín. 8 caracteres)</span>
            </label>
            <input
              id="registro-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-lg border border-border bg-surface/40 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              placeholder="••••••••"
            />
          </div>

          {/* Age confirmation — required, not pre-checked */}
          <div className="flex flex-col gap-2 rounded-lg border border-border/60 bg-surface/30 p-3">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                id="registro-age"
                type="checkbox"
                checked={ageConfirmed}
                onChange={(e) => {
                  setAgeConfirmed(e.target.checked)
                  if (e.target.checked) setAgeError(false)
                }}
                className="mt-0.5 size-4 shrink-0 accent-primary"
              />
              <span className="text-xs text-foreground leading-relaxed">
                Confirmo que soy mayor de 18 años
              </span>
            </label>
            {ageError && (
              <p role="alert" className="text-xs font-medium text-negative">
                Necesitás confirmar que sos mayor de 18 años para crear una cuenta.
              </p>
            )}
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              BetMind no opera casas de apuestas ni gestiona tu dinero de apuesta. Es una herramienta
              de análisis estadístico. Apostar implica riesgo — no garantiza ganancias.
            </p>
          </div>

          <button
            type="submit"
            id="registro-submit"
            disabled={loading}
            className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Creando cuenta…' : 'Crear cuenta gratis'}
          </button>
        </form>
      </div>
    </div>
  )
}
