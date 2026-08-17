-- Migration 025: daily_unlocks — cuota de desbloqueos diarios del plan gratuito.
-- Nuevo modelo freemium: un usuario registrado sin PRO puede desbloquear hasta
-- 3 partidos por día COT (America/Bogota), los que él elija, para ver el
-- análisis completo. Una fila = un partido desbloqueado por un usuario en una
-- fecha COT. El reset es implícito: la cuota del día siguiente se calcula
-- contra su propio unlock_date.
--
-- Reemplaza los topes viejos de Redis (generación 2/día y guardado anónimo
-- 5/día por IP), que se retiran de tickets.py.

CREATE TABLE IF NOT EXISTS daily_unlocks (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id     INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    unlock_date  DATE NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ,
    CONSTRAINT uq_daily_unlocks_user_match_date UNIQUE (user_id, match_id, unlock_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_unlocks_user_date ON daily_unlocks (user_id, unlock_date);
CREATE INDEX IF NOT EXISTS idx_daily_unlocks_match_id ON daily_unlocks (match_id);

-- RLS: lectura solo de los propios desbloqueos (mismo patrón que 019). Las
-- escrituras las hace exclusivamente el backend FastAPI (rol postgres, que
-- ignora RLS por diseño).
ALTER TABLE public.daily_unlocks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS daily_unlocks_select_own ON public.daily_unlocks;
CREATE POLICY daily_unlocks_select_own ON public.daily_unlocks
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.users
            WHERE users.id = daily_unlocks.user_id
              AND users.auth_uid = auth.uid()
        )
    );