'use client'

import * as React from 'react'
import Link from 'next/link'

import { forgotPassword } from '@/lib/auth'

const NEUTRAL_MESSAGE =
  'Si el email existe en nuestro sistema, vas a recibir un link para restablecer tu contraseña.'

export default function OlvidePasswordPage() {
  const [email, setEmail] = React.useState('')
  const [sent, setSent] = React.useState(false)
  const [networkError, setNetworkError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setNetworkError(null)
    setLoading(true)
    try {
      await forgotPassword(email)
      // Always show neutral message whether the email exists or not
      setSent(true)
    } catch (err) {
      // Only surface network-level errors — never reveal if the email exists
      const msg = err instanceof Error ? err.message : ''
      const isNetwork = msg.toLowerCase().includes('network') || msg.toLowerCase().includes('conexión') || msg.toLowerCase().includes('fetch')
      setNetworkError(
        isNetwork
          ? 'Parece que no tenés conexión. Verificá tu red e intentá de nuevo.'
          : NEUTRAL_MESSAGE, // fall back to neutral even on unknown errors
      )
      if (!isNetwork) setSent(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-sm">
      <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Recuperar contraseña</h1>
        <p className="mb-6 text-sm text-muted-foreground">
          Ingresá tu email y te enviaremos las instrucciones.
        </p>

        {sent ? (
          <div className="flex flex-col gap-4">
            <div
              role="status"
              className="rounded-lg border border-positive/30 bg-positive/10 px-4 py-3 text-sm font-medium text-positive"
            >
              {NEUTRAL_MESSAGE}
            </div>
            <Link
              href="/cuenta/login"
              className="text-center text-sm font-semibold text-primary hover:underline"
            >
              Volver al inicio de sesión
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
            {networkError && !sent && (
              <div
                role="alert"
                className="rounded-lg border border-negative/30 bg-negative/10 px-4 py-3 text-sm font-medium text-negative"
              >
                {networkError}
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="forgot-email"
                className="text-xs font-semibold text-muted-foreground uppercase tracking-wider"
              >
                Email
              </label>
              <input
                id="forgot-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-lg border border-border bg-surface/40 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                placeholder="tu@email.com"
              />
            </div>

            <button
              type="submit"
              id="forgot-submit"
              disabled={loading}
              className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {loading ? 'Enviando…' : 'Enviar instrucciones'}
            </button>

            <Link
              href="/cuenta/login"
              className="text-center text-sm text-muted-foreground hover:text-foreground"
            >
              Volver al inicio de sesión
            </Link>
          </form>
        )}
      </div>
    </div>
  )
}
