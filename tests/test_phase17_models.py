"""Tests para Fase 17: Dixon-Coles, Binomial Negativa (Córneres), Player Props y MTI."""
import pytest
import math


class TestDixonColesCorrection:
    """Tests para la corrección Dixon-Coles en la matriz de Poisson."""

    def test_dixon_coles_matrix_sums_to_one(self):
        """La matriz corregida debe sumar exactamente 1.0."""
        from betmind_ml.models.poisson_engine import build_score_matrix

        matrix = build_score_matrix(lambda_home=1.5, lambda_away=1.2)
        total = sum(sum(row) for row in matrix.matrix)
        assert abs(total - 1.0) < 0.0001, f"Matrix sum = {total}, expected 1.0"

    def test_dixon_coles_increases_00_probability(self):
        """Dixon-Coles debe aumentar P(0-0) respecto a Poisson puro."""
        from betmind_ml.models.poisson_engine import (
            build_score_matrix,
            _apply_dixon_coles_correction,
            _renormalize_matrix,
        )
        from scipy.stats import poisson

        lambda_home, lambda_away = 1.5, 1.2
        rho = -0.09

        # Matriz Poisson pura
        p_00_pure = poisson.pmf(0, lambda_home) * poisson.pmf(0, lambda_away)

        # Matriz con Dixon-Coles
        size = 9
        pure_matrix = [[0.0] * size for _ in range(size)]
        for i in range(size):
            for j in range(size):
                pure_matrix[i][j] = poisson.pmf(i, lambda_home) * poisson.pmf(j, lambda_away)

        corrected = _apply_dixon_coles_correction(pure_matrix, lambda_home, lambda_away, rho)
        corrected = _renormalize_matrix(corrected)
        p_00_dc = corrected[0][0]

        assert p_00_dc > p_00_pure, (
            f"Dixon-Coles debe aumentar P(0-0): {p_00_dc:.6f} > {p_00_pure:.6f}"
        )

    def test_dixon_coles_tau_values(self):
        """Verificar valores τ para las 4 celdas críticas."""
        from betmind_ml.models.poisson_engine import _apply_dixon_coles_correction

        lambda_home, lambda_away = 1.5, 1.2
        rho = -0.09

        # Matriz identidad (solo para probar τ)
        size = 9
        identity = [[1.0 if i == j == 0 else 0.0 for j in range(size)] for i in range(size)]
        # Poner 1.0 en las 4 celdas críticas
        identity[0][0] = 1.0
        identity[1][0] = 1.0
        identity[0][1] = 1.0
        identity[1][1] = 1.0

        corrected = _apply_dixon_coles_correction(identity, lambda_home, lambda_away, rho)

        # τ(0,0) = 1 - (1.5 * 1.2 * -0.09) = 1 + 0.162 = 1.162
        expected_tau_00 = 1.0 - (lambda_home * lambda_away * rho)
        assert abs(corrected[0][0] - expected_tau_00) < 0.001

        # τ(1,0) = 1 + (1.2 * -0.09) = 1 - 0.108 = 0.892
        expected_tau_10 = 1.0 + (lambda_away * rho)
        assert abs(corrected[1][0] - expected_tau_10) < 0.001

        # τ(0,1) = 1 + (1.5 * -0.09) = 1 - 0.135 = 0.865
        expected_tau_01 = 1.0 + (lambda_home * rho)
        assert abs(corrected[0][1] - expected_tau_01) < 0.001

        # τ(1,1) = 1 - (-0.09) = 1.09
        expected_tau_11 = 1.0 - rho
        assert abs(corrected[1][1] - expected_tau_11) < 0.001

    def test_dixon_coles_other_cells_unchanged(self):
        """Celdas fuera de (0,0), (1,0), (0,1), (1,1) deben tener τ = 1.0."""
        from betmind_ml.models.poisson_engine import _apply_dixon_coles_correction

        size = 9
        ones_matrix = [[1.0 for _ in range(size)] for _ in range(size)]
        corrected = _apply_dixon_coles_correction(ones_matrix, 1.5, 1.2, -0.09)

        # Celdas (2,0), (0,2), (2,2), (3,5) etc. deben ser 1.0
        assert corrected[2][0] == 1.0
        assert corrected[0][2] == 1.0
        assert corrected[2][2] == 1.0
        assert corrected[3][5] == 1.0


class TestNegativeBinomialCorners:
    """Tests para modelo de córneres con Binomial Negativa."""

    def test_corners_probabilities_sum_to_one(self):
        """Over + Under deben sumar 1.0 para cada línea."""
        from apps.api.engine.corners_model import calculate_corners_probabilities

        probs = calculate_corners_probabilities(expected_corners=9.2)

        for line in [7.5, 8.5, 9.5, 10.5]:
            total = probs[f"over_{line}"] + probs[f"under_{line}"]
            assert abs(total - 1.0) < 0.001, f"Line {line}: sum = {total}"

    def test_corners_higher_expected_increases_over(self):
        """Mayor μ debe aumentar P(Over) para línea fija."""
        from apps.api.engine.corners_model import calculate_corners_line_probability

        probs_low = calculate_corners_line_probability(expected_corners=8.0, line=9.5)
        probs_high = calculate_corners_line_probability(expected_corners=11.0, line=9.5)

        assert probs_high["over"] > probs_low["over"], (
            f"μ=11 debe tener mayor P(Over) que μ=8: {probs_high['over']} > {probs_low['over']}"
        )

    def test_corners_recommendation_over(self):
        """Recomendación debe ser Over cuando P(Over) > 0.55."""
        from apps.api.engine.corners_model import get_corners_recommendation

        rec, prob = get_corners_recommendation(expected_corners=11.0, line=9.5)
        assert "Over" in rec
        assert prob > 0.55

    def test_corners_recommendation_under(self):
        """Recomendación debe ser Under cuando P(Under) > 0.55."""
        from apps.api.engine.corners_model import get_corners_recommendation

        rec, prob = get_corners_recommendation(expected_corners=7.5, line=9.5)
        assert "Under" in rec
        assert prob > 0.55

    def test_corners_dispersion_parameter(self):
        """Verificar que k=1.3 produce varianza = 1.3 * μ."""
        from apps.api.engine.corners_model import K_DISPERSION

        assert K_DISPERSION == 1.3

        # Para μ=10: Varianza esperada = 1.3 * 10 = 13
        # Binomial Negativa: Var = r * (1-p) / p^2
        # Con p = 1/k = 1/1.3, r = μ/(k-1) = 10/0.3
        p = 1.0 / K_DISPERSION
        r = 10.0 / (K_DISPERSION - 1)
        variance = r * (1 - p) / (p ** 2)
        expected_variance = K_DISPERSION * 10.0

        assert abs(variance - expected_variance) < 0.1


class TestPlayerPropsValidation:
    """Tests para validación de Player Props con minutos proyectados."""

    def test_player_prop_available_with_90_minutes(self):
        """Jugador con 90 min y confirmado debe estar AVAILABLE."""
        from apps.api.engine.player_props_model import (
            calculate_player_prop_projection,
            PlayerPropStatus,
        )

        proj = calculate_player_prop_projection(
            player_name="Luis Díaz",
            stat_type="shots_on_target",
            stat_per_90=2.5,
            projected_minutes=90,
            is_confirmed_starter=True,
            opponent_defense_factor=1.1,
        )

        assert proj.status == PlayerPropStatus.AVAILABLE
        assert proj.expected_stat > 0
        # expected = 2.5 * (90/90) * 1.1 = 2.75
        assert abs(proj.expected_stat - 2.75) < 0.01

    def test_player_prop_not_available_under_60_minutes(self):
        """Jugador con < 60 min debe estar NOT_AVAILABLE."""
        from apps.api.engine.player_props_model import (
            calculate_player_prop_projection,
            PlayerPropStatus,
        )

        proj = calculate_player_prop_projection(
            player_name="Radamel Falcao",
            stat_type="shots_on_target",
            stat_per_90=3.0,
            projected_minutes=45,
            is_confirmed_starter=True,
        )

        assert proj.status == PlayerPropStatus.NOT_AVAILABLE
        assert proj.expected_stat == 0.0

    def test_player_prop_not_available_not_starter(self):
        """Jugador no confirmado en titular debe estar NOT_AVAILABLE."""
        from apps.api.engine.player_props_model import (
            calculate_player_prop_projection,
            PlayerPropStatus,
        )

        proj = calculate_player_prop_projection(
            player_name="James Rodríguez",
            stat_type="shots_on_target",
            stat_per_90=2.0,
            projected_minutes=90,
            is_confirmed_starter=False,
        )

        assert proj.status == PlayerPropStatus.NOT_AVAILABLE
        assert proj.expected_stat == 0.0

    def test_player_prop_partial_minutes_calculation(self):
        """Cálculo correcto con minutos parciales (75 min)."""
        from apps.api.engine.player_props_model import (
            calculate_player_prop_projection,
            PlayerPropStatus,
        )

        proj = calculate_player_prop_projection(
            player_name="Duván Zapata",
            stat_type="total_shots",
            stat_per_90=4.0,
            projected_minutes=75,
            is_confirmed_starter=True,
            opponent_defense_factor=1.0,
        )

        assert proj.status == PlayerPropStatus.AVAILABLE
        # expected = 4.0 * (75/90) * 1.0 = 3.33
        assert abs(proj.expected_stat - 3.33) < 0.01

    def test_player_prop_defense_factor_impact(self):
        """Factor defensivo del rival debe escalar la proyección."""
        from apps.api.engine.player_props_model import calculate_player_prop_projection

        # Rival débil (factor > 1)
        proj_weak = calculate_player_prop_projection(
            player_name="Test",
            stat_type="shots_on_target",
            stat_per_90=2.0,
            projected_minutes=90,
            is_confirmed_starter=True,
            opponent_defense_factor=1.3,
        )

        # Rival fuerte (factor < 1)
        proj_strong = calculate_player_prop_projection(
            player_name="Test",
            stat_type="shots_on_target",
            stat_per_90=2.0,
            projected_minutes=90,
            is_confirmed_starter=True,
            opponent_defense_factor=0.8,
        )

        assert proj_weak.expected_stat > proj_strong.expected_stat


class TestMatchTensionIndex:
    """Tests para el Índice de Tensión del Partido (MTI)."""

    def test_mti_regular_match(self):
        """Partido regular debe tener MTI = 1.0."""
        from apps.api.engine.match_tension import (
            get_match_tension_index,
            MatchContextType,
        )

        mti = get_match_tension_index(MatchContextType.REGULAR)
        assert mti == 1.0

    def test_mti_classification_clash(self):
        """Duelo por clasificación debe tener MTI = 1.15."""
        from apps.api.engine.match_tension import (
            get_match_tension_index,
            MatchContextType,
        )

        mti = get_match_tension_index(MatchContextType.CLASSIFICATION_CLASH)
        assert mti == 1.15

    def test_mti_derby(self):
        """Derby/Clásico debe tener MTI = 1.35."""
        from apps.api.engine.match_tension import (
            get_match_tension_index,
            MatchContextType,
        )

        mti = get_match_tension_index(MatchContextType.DERBY)
        assert mti == 1.35

    def test_mti_relegation(self):
        """Partido por descenso debe tener MTI = 1.35."""
        from apps.api.engine.match_tension import (
            get_match_tension_index,
            MatchContextType,
        )

        mti = get_match_tension_index(MatchContextType.RELEGATION)
        assert mti == 1.35

    def test_projected_cards_with_mti(self):
        """Cálculo de tarjetas proyectadas con MTI."""
        from apps.api.engine.match_tension import (
            calculate_projected_cards,
            MatchContextType,
        )

        # Base: 4.0 tarjetas, árbitro estricto (1.2), derby (1.35)
        projected, mti = calculate_projected_cards(
            base_cards_average=4.0,
            referee_strictness=1.2,
            context_type=MatchContextType.DERBY,
        )

        assert mti == 1.35
        # 4.0 * 1.2 * 1.35 = 6.48
        assert abs(projected - 6.48) < 0.01

    def test_projected_cards_regular_match(self):
        """Partido regular no debe inflar tarjetas."""
        from apps.api.engine.match_tension import (
            calculate_projected_cards,
            MatchContextType,
        )

        projected, mti = calculate_projected_cards(
            base_cards_average=4.0,
            referee_strictness=1.0,
            context_type=MatchContextType.REGULAR,
        )

        assert mti == 1.0
        assert projected == 4.0

    def test_infer_context_type_derby(self):
        """Inferencia de contexto: derby."""
        from apps.api.engine.match_tension import (
            infer_context_type,
            MatchContextType,
        )

        ctx = infer_context_type(is_derby=True)
        assert ctx == MatchContextType.DERBY

    def test_infer_context_type_relegation(self):
        """Inferencia de contexto: descenso."""
        from apps.api.engine.match_tension import (
            infer_context_type,
            MatchContextType,
        )

        ctx = infer_context_type(is_relegation_battle=True)
        assert ctx == MatchContextType.RELEGATION

    def test_infer_context_type_default(self):
        """Inferencia de contexto: default es REGULAR."""
        from apps.api.engine.match_tension import (
            infer_context_type,
            MatchContextType,
        )

        ctx = infer_context_type()
        assert ctx == MatchContextType.REGULAR
