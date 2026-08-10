-- Migración 019: RLS estricto (solo lectura) para subscriptions y subscription_transactions.
-- Arquitectura: los clientes (Next.js) tienen SOLO SELECT de sus propios registros.
-- Las escrituras financieras las hace exclusivamente el backend FastAPI
-- (rol postgres con BYPASSRLS), que ignora RLS por diseño.

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_transactions ENABLE ROW LEVEL SECURITY;

-- 1) Suscripciones: cada usuario lee solo las suyas.
--    user_id (int, FK users.id) se mapea a auth.uid() vía users.auth_uid (uuid).
DROP POLICY IF EXISTS subscriptions_select_own ON public.subscriptions;
CREATE POLICY subscriptions_select_own ON public.subscriptions
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.users
            WHERE users.id = subscriptions.user_id
              AND users.auth_uid = auth.uid()
        )
    );

-- 2) Transacciones: solo las de suscripciones del usuario autenticado.
DROP POLICY IF EXISTS subscription_transactions_select_own ON public.subscription_transactions;
CREATE POLICY subscription_transactions_select_own ON public.subscription_transactions
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.subscriptions s
            JOIN public.users u ON u.id = s.user_id
            WHERE s.id = subscription_transactions.subscription_id
              AND u.auth_uid = auth.uid()
        )
    );

-- Nota deliberada: NO existen políticas INSERT/UPDATE/DELETE para clientes.
-- Con RLS activo y sin políticas de escritura, anon/authenticated no pueden
-- modificar ninguna fila de estas tablas.
