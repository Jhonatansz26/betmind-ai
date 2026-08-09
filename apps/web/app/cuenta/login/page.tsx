'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

import { login } from '@/lib/auth'
import { claimPendingTickets } from '@/components/betmind/tracking-panel'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      // Task 5: claim anonymous tickets silently
      claimPendingTickets().catch((err: unknown) => console.error('[claim]', err))
      // Redirect to ?redirect= param or home
      const params = new URLSearchParams(window.location.search)
      router.push(params.get('redirect') ?? '/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Email o contraseña incorrectos.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-sm">
      <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Iniciar sesión</h1>
        <p className="mb-6 text-sm text-muted-foreground">
          ¿No tenés cuenta?{' '}
          <Link href="/cuenta/registro" className="font-semibold text-primary hover:underline">
            Crear cuenta gratis
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
            <label htmlFor="login-email" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Email
            </label>
            <input
              id="login-email"
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
            <div className="flex items-center justify-between">
              <label htmlFor="login-password" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Contraseña
              </label>
              <Link
                href="/cuenta/olvide-password"
                className="text-xs text-primary hover:underline"
              >
                ¿Olvidaste tu contraseña?
              </Link>
            </div>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-lg border border-border bg-surface/40 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            id="login-submit"
            disabled={loading}
            className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Iniciando sesión…' : 'Iniciar sesión'}
          </button>
        </form>
      </div>
    </div>
  )
}
