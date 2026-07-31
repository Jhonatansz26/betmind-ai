-- 007_add_match_statistics_columns.sql
-- Añade columnas de estadísticas (córneres, tarjetas, faltas, remates a puerta) a la tabla matches
-- para habilitar mercados de corners, tarjetas y remates en el pipeline predictivo.

ALTER TABLE matches
  ADD COLUMN IF NOT EXISTS home_corners INTEGER,
  ADD COLUMN IF NOT EXISTS away_corners INTEGER,
  ADD COLUMN IF NOT EXISTS home_yellows FLOAT,
  ADD COLUMN IF NOT EXISTS away_yellows FLOAT,
  ADD COLUMN IF NOT EXISTS home_reds FLOAT,
  ADD COLUMN IF NOT EXISTS away_reds FLOAT,
  ADD COLUMN IF NOT EXISTS home_fouls FLOAT,
  ADD COLUMN IF NOT EXISTS away_fouls FLOAT,
  ADD COLUMN IF NOT EXISTS home_shots_on_target FLOAT,
  ADD COLUMN IF NOT EXISTS away_shots_on_target FLOAT;
