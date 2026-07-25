"""
Test unitario para el motor de Poisson.
Verifica que run_prediction() funcione correctamente y calcule las probabilidades.
"""
from betmind_ml.pipeline.prediction_pipeline import run_prediction
from betmind_ml.schemas.prediction_output import PredictionVerdict


def test_run_prediction_basic():
    """Test básico del pipeline de predicción."""
    # Datos de prueba simulados
    home_matches = [
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 3, "home_goals": 3, "away_goals": 0},
        {"home_team_id": 4, "away_team_id": 1, "home_goals": 1, "away_goals": 2},
        {"home_team_id": 1, "away_team_id": 5, "home_goals": 1, "away_goals": 1},
        {"home_team_id": 6, "away_team_id": 1, "home_goals": 0, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 7, "home_goals": 2, "away_goals": 0},
    ]
    
    away_matches = [
        {"home_team_id": 2, "away_team_id": 8, "home_goals": 1, "away_goals": 0},
        {"home_team_id": 9, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
        {"home_team_id": 2, "away_team_id": 10, "home_goals": 0, "away_goals": 0},
        {"home_team_id": 11, "away_team_id": 2, "home_goals": 1, "away_goals": 2},
        {"home_team_id": 2, "away_team_id": 12, "home_goals": 3, "away_goals": 1},
        {"home_team_id": 13, "away_team_id": 2, "home_goals": 0, "away_goals": 1},
    ]
    
    all_league_matches = home_matches + away_matches + [
        {"home_team_id": 14, "away_team_id": 15, "home_goals": 2, "away_goals": 2},
        {"home_team_id": 16, "away_team_id": 17, "home_goals": 1, "away_goals": 0},
        {"home_team_id": 18, "away_team_id": 19, "home_goals": 0, "away_goals": 3},
        {"home_team_id": 20, "away_team_id": 21, "home_goals": 2, "away_goals": 1},
    ]
    
    h2h_matches = [
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
        {"home_team_id": 2, "away_team_id": 1, "home_goals": 0, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 1, "away_goals": 0},
    ]
    
    # Ejecutar predicción
    output = run_prediction(
        match_id=123,
        home_team_id=1,
        home_team_name="Millonarios",
        away_team_id=2,
        away_team_name="Nacional",
        league_id=239,
        league_key="liga_betplay",
        season=2026,
        home_matches=home_matches,
        away_matches=away_matches,
        all_league_matches=all_league_matches,
        h2h_matches=h2h_matches,
    )
    
    # Verificaciones básicas
    assert output.match_id == 123
    assert output.lambda_home > 0
    assert output.lambda_away > 0
    assert output.lambda_home < 6.0
    assert output.lambda_away < 6.0
    
    # Verificar que se generaron mercados
    assert len(output.markets) > 0
    
    # Verificar mercados principales
    market_names = [m.market_name for m in output.markets]
    assert "1X2_HOME" in market_names
    assert "1X2_DRAW" in market_names
    assert "1X2_AWAY" in market_names
    assert "OVER_2_5" in market_names
    assert "BTTS_YES" in market_names
    
    # Verificar matriz de scores
    assert output.score_matrix.matrix is not None
    assert len(output.score_matrix.matrix) > 0
    assert output.score_matrix.most_likely_score != ""
    assert output.score_matrix.most_likely_prob > 0
    
    # Verificar confianza
    assert 0 <= output.confidence_score <= 100
    
    print("[OK] Test basico de prediccion completado")
    print(f"  lambda_home={output.lambda_home:.3f}, lambda_away={output.lambda_away:.3f}")
    print(f"  Score mas probable: {output.score_matrix.most_likely_score} ({output.score_matrix.most_likely_prob*100:.1f}%)")
    print(f"  Confianza: {output.confidence_score}/100")


def test_run_prediction_with_odds():
    """Test del pipeline con cuotas de bookmaker para cálculo de EV."""
    home_matches = [
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 3, "home_goals": 3, "away_goals": 0},
        {"home_team_id": 4, "away_team_id": 1, "home_goals": 1, "away_goals": 2},
        {"home_team_id": 1, "away_team_id": 5, "home_goals": 1, "away_goals": 1},
        {"home_team_id": 6, "away_team_id": 1, "home_goals": 0, "away_goals": 1},
    ]
    
    away_matches = [
        {"home_team_id": 2, "away_team_id": 8, "home_goals": 1, "away_goals": 0},
        {"home_team_id": 9, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
        {"home_team_id": 2, "away_team_id": 10, "home_goals": 0, "away_goals": 0},
        {"home_team_id": 11, "away_team_id": 2, "home_goals": 1, "away_goals": 2},
        {"home_team_id": 2, "away_team_id": 12, "home_goals": 3, "away_goals": 1},
    ]
    
    all_league_matches = home_matches + away_matches
    
    h2h_matches = []
    
    # Cuotas de bookmaker simuladas
    bookmaker_odds = {
        "1X2_HOME": 2.10,
        "1X2_DRAW": 3.40,
        "1X2_AWAY": 3.50,
        "OVER_2_5": 1.85,
        "BTTS_YES": 1.75,
    }
    
    # Ejecutar predicción con cuotas
    output = run_prediction(
        match_id=456,
        home_team_id=1,
        home_team_name="Millonarios",
        away_team_id=2,
        away_team_name="Nacional",
        league_id=239,
        league_key="liga_betplay",
        season=2026,
        home_matches=home_matches,
        away_matches=away_matches,
        all_league_matches=all_league_matches,
        h2h_matches=h2h_matches,
        bookmaker_odds=bookmaker_odds,
    )
    
    # Verificar que se calculó EV
    markets_with_ev = [m for m in output.markets if m.expected_value is not None]
    assert len(markets_with_ev) > 0
    
    # Verificar que algunos mercados tienen verdict
    markets_with_verdict = [m for m in output.markets if m.verdict != PredictionVerdict.INSUFFICIENT]
    assert len(markets_with_verdict) > 0
    
    print("[OK] Test de prediccion con cuotas completado")
    print(f"  Mercados con EV calculado: {len(markets_with_ev)}")
    print(f"  Mercados con verdict: {len(markets_with_verdict)}")


def test_poisson_matrix_sum():
    """Verifica que la matriz de Poisson suma aproximadamente 1.0."""
    from betmind_ml.models.poisson_engine import build_score_matrix
    
    lambda_home = 1.5
    lambda_away = 1.2
    
    score_matrix = build_score_matrix(lambda_home, lambda_away)
    
    # Sumar toda la matriz
    total_prob = sum(
        score_matrix.matrix[i][j]
        for i in range(len(score_matrix.matrix))
        for j in range(len(score_matrix.matrix[i]))
    )
    
    # Debe sumar aproximadamente 1.0 (con margen por truncamiento)
    assert 0.95 <= total_prob <= 1.05, f"La matriz suma {total_prob}, debería ser ~1.0"
    
    print(f"[OK] Test de suma de matriz completado: {total_prob:.4f}")


def test_1x2_probabilities_sum():
    """Verifica que las probabilidades 1X2 suman 1.0."""
    from betmind_ml.models.poisson_engine import build_score_matrix
    from betmind_ml.models.market_calculator import calculate_1x2
    
    lambda_home = 1.8
    lambda_away = 1.0
    
    score_matrix = build_score_matrix(lambda_home, lambda_away)
    probs_1x2 = calculate_1x2(score_matrix.matrix)
    
    total = probs_1x2["home_win"] + probs_1x2["draw"] + probs_1x2["away_win"]
    
    # Debe sumar 1.0 (normalizado)
    assert 0.99 <= total <= 1.01, f"1X2 suma {total}, debería ser ~1.0"
    
    print(f"[OK] Test de probabilidades 1X2 completado: {total:.4f}")
    print(f"  Home: {probs_1x2['home_win']*100:.1f}%, Draw: {probs_1x2['draw']*100:.1f}%, Away: {probs_1x2['away_win']*100:.1f}%")


if __name__ == "__main__":
    test_run_prediction_basic()
    test_run_prediction_with_odds()
    test_poisson_matrix_sum()
    test_1x2_probabilities_sum()
    print("\n[OK] Todos los tests completados exitosamente")
