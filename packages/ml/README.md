# BetMind ML - Motor Predictivo Cuantitativo

Motor de predicción deportiva basado en distribución de Poisson bivariada y cálculo de valor esperado positivo (+EV).

## Características

- **Modelo de Poisson Bivariado**: Predicción de goles esperados (xG) usando índices de ataque/defensa relativos a la liga
- **Cálculo de Mercados**: 1X2, Over/Under, BTTS desde matriz de probabilidades
- **Valor Esperado (+EV)**: Detección de apuestas con valor real comparando probabilidades vs cuotas
- **Feature Engineering**: Cálculo automático de fuerza de equipos, forma reciente y H2H
- **Regla de 90 Minutos**: Todos los análisis consideran exclusivamente tiempo reglamentario

## Instalación

```bash
pip install -e packages/ml
```

## Uso

```python
from betmind_ml.pipeline.prediction_pipeline import run_prediction

output = run_prediction(
    match_id=123,
    home_team_id=1,
    home_team_name="Millonarios",
    away_team_id=2,
    away_team_name="Nacional",
    league_id=239,
    league_key="liga_betplay",
    season=2026,
    home_matches=[...],
    away_matches=[...],
    all_league_matches=[...],
    h2h_matches=[...],
    bookmaker_odds={"1X2_HOME": 2.10, "OVER_2_5": 1.85},
)

print(f"λ_home={output.lambda_home:.2f}, λ_away={output.lambda_away:.2f}")
print(f"Score más probable: {output.score_matrix.most_likely_score}")
```

## Arquitectura

```
betmind_ml/
├── schemas/          # Contratos de datos (SDD)
├── features/         # Feature engineering (fuerza, forma, H2H)
├── models/           # Modelos matemáticos (Poisson, mercados)
├── ev/               # Cálculo de valor esperado
├── pipeline/         # Orquestación del flujo completo
└── backtesting/      # Validación del modelo (Fase 4)
```

## Fundamento Matemático

**Distribución de Poisson:**
```
P(X=i) = (λ^i * e^(-λ)) / i!
```

**Lambdas (goles esperados):**
```
λ_home = attack_home * defense_away * league_avg * home_advantage * form_adj
λ_away = attack_away * defense_home * league_avg * form_adj
```

**Valor Esperado:**
```
EV = (P_real * (cuota - 1)) - (1 - P_real)
```

## Licencia

Proprietary - BetMind AI
