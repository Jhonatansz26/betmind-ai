-- Migración 021: Línea de apertura verdadera en bookmaker_odds
--
-- Problema: upsert_odds hace UPDATE in-place sobre (match_id, market_name,
-- bookmaker_name) — no había historial, así que el CLV medía drift de
-- sincronización y no el edge contra la línea de apertura verdadera.
--
-- Solución: opening_odds_value se escribe UNA sola vez, en el primer insert
-- de cada fila. Los upserts posteriores NO lo tocan.
--
-- Nota: las filas creadas ANTES de esta migración quedan con
-- opening_odds_value = NULL (la apertura verdadera ya se perdió); el job de
-- CLV las omite hasta que haya filas nuevas con apertura real.
-- NO se backfillea con odds_value actual: eso sería atribuir la línea de
-- hoy como "apertura" y repetir el mismo sesgo.

ALTER TABLE public.bookmaker_odds
    ADD COLUMN IF NOT EXISTS opening_odds_value DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS opening_odds_captured_at TIMESTAMPTZ;

COMMENT ON COLUMN public.bookmaker_odds.opening_odds_value IS
    'Cuota del primer sync (línea de apertura verdadera). Se escribe una sola vez y nunca se sobrescribe.';
COMMENT ON COLUMN public.bookmaker_odds.opening_odds_captured_at IS
    'Timestamp del primer sync en el que se capturó la línea de apertura.';
