-- Migración 004: Crear tabla tactical_analyses
-- Fase 4: Motor Táctico y Narrativo

CREATE TABLE IF NOT EXISTS tactical_analyses (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL UNIQUE REFERENCES matches(id) ON DELETE CASCADE,
    
    -- Versión del modelo narrativo utilizado
    model_version VARCHAR(50) NOT NULL DEFAULT 'narrative_v1.0',
    
    -- Narrativas de mercados (JSONB para flexibilidad)
    goals_narrative JSONB,
    cards_narrative JSONB,
    corners_narrative JSONB,
    player_props_narratives JSONB,
    
    -- Combinaciones bet builder sugeridas
    bet_builder_suggestions JSONB,
    
    -- Métricas de confianza y calidad
    overall_confidence INTEGER NOT NULL DEFAULT 0,
    match_preview_headline VARCHAR(200) NOT NULL,
    
    -- Metadata del LLM
    llm_model_used VARCHAR(100) NOT NULL DEFAULT '',
    generation_tokens_used INTEGER NOT NULL DEFAULT 0,
    data_completeness_score DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    
    -- Timestamps automáticos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Habilitar Row Level Security (RLS) por seguridad de Supabase
ALTER TABLE tactical_analyses ENABLE ROW LEVEL SECURITY;

-- Política de lectura pública (para la API/App)
CREATE POLICY "Allow public read access to tactical_analyses" 
    ON tactical_analyses FOR SELECT 
    USING (true);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_tactical_analyses_match_id ON tactical_analyses(match_id);
CREATE INDEX IF NOT EXISTS idx_tactical_analyses_created_at ON tactical_analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tactical_analyses_overall_confidence ON tactical_analyses(overall_confidence DESC);

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_tactical_analyses_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar updated_at en cada UPDATE
DROP TRIGGER IF EXISTS trigger_tactical_analyses_updated_at ON tactical_analyses;
CREATE TRIGGER trigger_tactical_analyses_updated_at
    BEFORE UPDATE ON tactical_analyses
    FOR EACH ROW
    EXECUTE FUNCTION update_tactical_analyses_updated_at();

-- Comentarios para documentación
COMMENT ON TABLE tactical_analyses IS 'Análisis táctico completo generado por el Cerebro Táctico (Fase 4) con LLM';
COMMENT ON COLUMN tactical_analyses.match_id IS 'ID del partido (relación 1:1)';
COMMENT ON COLUMN tactical_analyses.model_version IS 'Versión del modelo narrativo (ej: narrative_v1.0)';
COMMENT ON COLUMN tactical_analyses.goals_narrative IS 'Análisis narrativo del mercado de goles (Over/Under, BTTS)';
COMMENT ON COLUMN tactical_analyses.cards_narrative IS 'Análisis narrativo del mercado de tarjetas';
COMMENT ON COLUMN tactical_analyses.corners_narrative IS 'Análisis narrativo del mercado de córneres';
COMMENT ON COLUMN tactical_analyses.player_props_narratives IS 'Análisis narrativo de props de jugadores';
COMMENT ON COLUMN tactical_analyses.bet_builder_suggestions IS 'Combinaciones bet builder sugeridas con correlación';
COMMENT ON COLUMN tactical_analyses.overall_confidence IS 'Confianza global del análisis táctico (0-100)';
COMMENT ON COLUMN tactical_analyses.match_preview_headline IS 'Titular periodístico del partido';
COMMENT ON COLUMN tactical_analyses.llm_model_used IS 'Modelo LLM utilizado (ej: llama-3.3-70b-versatile)';
COMMENT ON COLUMN tactical_analyses.generation_tokens_used IS 'Tokens consumidos en la generación';
COMMENT ON COLUMN tactical_analyses.data_completeness_score IS 'Score de completitud de datos (0.0-1.0)';