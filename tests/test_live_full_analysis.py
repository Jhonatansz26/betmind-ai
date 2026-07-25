"""
Prueba de integración End-to-End del Cerebro Táctico con API real de Groq.
Ejecuta el pipeline completo (Fase 3 + Fase 4) con datos mock realistas.
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Agregar packages/ml al path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "ml"))

from dotenv import load_dotenv
from groq import Groq

# Cargar variables de entorno
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from betmind_ml.pipeline.full_analysis_pipeline import run_full_analysis
from betmind_ml.schemas.match_context import MatchContext, MatchImportance
from betmind_ml.schemas.referee import RefereeProfile


def list_groq_models(api_key: str):
    """Lista todos los modelos de Groq disponibles para la API key."""
    print("\n" + "=" * 80)
    print("🤖 DIAGNÓSTICO: Modelos de Groq Disponibles")
    print("=" * 80)
    
    try:
        client = Groq(api_key=api_key)
        models = client.models.list()
        
        print(f"\n✅ Total de modelos disponibles: {len(models.data)}\n")
        
        for i, model in enumerate(models.data[:15], 1):
            print(f"  {i}. {model.id}")
        
        print("\n" + "=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ Error listando modelos: {e}")
        return False


def build_mock_data():
    """Construye datos mock realistas para Atlético Nacional vs Millonarios."""
    
    # Datos de partidos recientes del local (Nacional en casa)
    home_matches = [
        {"home_team_id": 1, "away_team_id": 3, "home_goals": 3, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 5, "home_goals": 2, "away_goals": 0},
        {"home_team_id": 4, "away_team_id": 1, "home_goals": 1, "away_goals": 2},
        {"home_team_id": 1, "away_team_id": 7, "home_goals": 4, "away_goals": 2},
        {"home_team_id": 6, "away_team_id": 1, "home_goals": 0, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 9, "home_goals": 2, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 11, "home_goals": 3, "away_goals": 0},
        {"home_team_id": 12, "away_team_id": 1, "home_goals": 1, "away_goals": 1},
    ]
    
    # Datos de partidos recientes del visitante (Millonarios fuera)
    away_matches = [
        {"home_team_id": 2, "away_team_id": 8, "home_goals": 1, "away_goals": 2},
        {"home_team_id": 10, "away_team_id": 2, "home_goals": 0, "away_goals": 1},
        {"home_team_id": 2, "away_team_id": 14, "home_goals": 2, "away_goals": 2},
        {"home_team_id": 16, "away_team_id": 2, "home_goals": 1, "away_goals": 3},
        {"home_team_id": 2, "away_team_id": 18, "home_goals": 1, "away_goals": 0},
        {"home_team_id": 20, "away_team_id": 2, "home_goals": 2, "away_goals": 2},
        {"home_team_id": 2, "away_team_id": 22, "home_goals": 3, "away_goals": 1},
        {"home_team_id": 24, "away_team_id": 2, "home_goals": 0, "away_goals": 2},
    ]
    
    # Partidos de la liga (para calcular promedios)
    all_league_matches = home_matches + away_matches + [
        {"home_team_id": 25, "away_team_id": 26, "home_goals": 2, "away_goals": 1},
        {"home_team_id": 27, "away_team_id": 28, "home_goals": 1, "away_goals": 1},
        {"home_team_id": 29, "away_team_id": 30, "home_goals": 0, "away_goals": 2},
        {"home_team_id": 31, "away_team_id": 32, "home_goals": 3, "away_goals": 2},
        {"home_team_id": 33, "away_team_id": 34, "home_goals": 1, "away_goals": 0},
        {"home_team_id": 35, "away_team_id": 36, "home_goals": 2, "away_goals": 2},
        {"home_team_id": 37, "away_team_id": 38, "home_goals": 0, "away_goals": 1},
        {"home_team_id": 39, "away_team_id": 40, "home_goals": 4, "away_goals": 3},
    ]
    
    # H2H entre Nacional y Millonarios
    h2h_matches = [
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
        {"home_team_id": 2, "away_team_id": 1, "home_goals": 1, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 3, "away_goals": 2},
        {"home_team_id": 2, "away_team_id": 1, "home_goals": 0, "away_goals": 2},
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 1, "away_goals": 0},
    ]
    
    # Perfil del árbitro (estricto, con experiencia en derbis)
    referee = RefereeProfile(
        referee_name="Wilmar Roldán",
        matches_sample=45,
        avg_yellow_cards=4.8,
        avg_red_cards=0.3,
        avg_fouls_called=26.5,
        strictness_index=1.35,
        high_stakes_avg_yellows=5.6,
        recent_avg_yellow_cards=5.1,
        recent_trend="increasing",
        is_reliable=True,
    )
    
    # Contexto del partido (derby de alta intensidad en Medellín)
    context = MatchContext(
        match_id=999,
        stadium_altitude_masl=1500,
        expected_temperature_celsius=24.0,
        expected_weather="sunny",
        match_importance=MatchImportance.DERBY,
        is_derby=True,
        rivalry_intensity=5,
        home_position=2,
        away_position=3,
        home_games_without_win=0,
        away_games_without_win=1,
        home_days_since_last_match=5,
        away_days_since_last_match=4,
        home_matches_last_30_days=6,
        away_matches_last_30_days=7,
        is_midweek_match=False,
        home_key_players_out=["Jefferson Duque (lesionado)"],
        away_key_players_out=["David Macalister (suspendido)"],
    )
    
    # Datos adicionales para narrativa
    extra_data = {
        "home_fouls_avg": 14.2,
        "away_fouls_avg": 13.8,
        "home_yellows_avg": 2.4,
        "away_yellows_avg": 2.1,
        "home_booked_players": ["Dylan Franco", "Andrés Andrade"],
        "away_booked_players": ["Daniel Ruiz", "Jader Obrian"],
        "corners_data": {
            "home_corners_for_avg": 5.8,
            "home_corners_against_avg": 4.2,
            "home_blocked_shots_avg": 3.5,
            "home_tactical_style": "Posesión ofensiva por bandas",
            "away_corners_for_avg": 4.9,
            "away_corners_against_avg": 5.1,
            "away_blocked_shots_avg": 2.8,
            "away_tactical_style": "Contraataque rápido",
            "expected_corners_home": 6.2,
            "expected_corners_away": 4.8,
            "expected_corners_total": 11.0,
            "h2h_corners_avg": 10.5,
            "h2h_over_corners_count": 4,
            "h2h_count": 5,
            "corners_line": 9.5,
            "home_high_press_index": "Alto",
            "away_wide_play_index": "Medio",
        },
    }
    
    return {
        "match_id": 999,
        "home_team_id": 1,
        "home_team_name": "Atlético Nacional",
        "away_team_id": 2,
        "away_team_name": "Millonarios",
        "league_id": 239,
        "league_key": "liga_betplay",
        "league_name": "Liga BetPlay Dimayor 2026",
        "season": 2026,
        "match_date": "2026-07-26",
        "home_matches": home_matches,
        "away_matches": away_matches,
        "all_league_matches": all_league_matches,
        "h2h_matches": h2h_matches,
        "context": context,
        "referee": referee,
        "bookmaker_odds": {
            "1X2_HOME": 2.10,
            "1X2_DRAW": 3.40,
            "1X2_AWAY": 3.50,
            "OVER_2_5": 1.85,
            "UNDER_2_5": 1.95,
            "BTTS_YES": 1.75,
            "BTTS_NO": 2.05,
            "CARDS_OVER_3_5": 1.90,
            "CARDS_UNDER_3_5": 1.90,
            "CORNERS_OVER_9_5": 1.80,
            "CORNERS_UNDER_9_5": 2.00,
        },
        **extra_data,
    }


def print_results(quant_output, tactical_output, elapsed_time):
    """Imprime los resultados de forma estética y organizada."""
    
    print("\n" + "=" * 80)
    print("🧠 CEREBRO TÁCTICO — ANÁLISIS COMPLETO")
    print("=" * 80)
    
    # Titular y confianza
    print(f"\n📰 {tactical_output.match_preview_headline}")
    print(f"\n🎯 Confianza Global: {tactical_output.overall_confidence}/100")
    print(f"📊 Completitud de Datos: {tactical_output.data_completeness_score:.0%}")
    print(f"⚡ Tiempo de Respuesta: {elapsed_time:.2f}s")
    print(f"🤖 Modelo LLM: {tactical_output.llm_model_used}")
    
    # Motor Cuantitativo (Fase 3)
    print("\n" + "-" * 80)
    print("📈 MOTOR CUANTITATIVO (Poisson)")
    print("-" * 80)
    print(f"  λ Local (xG): {quant_output.lambda_home:.3f}")
    print(f"  λ Visitante (xG): {quant_output.lambda_away:.3f}")
    print(f"  Marcador más probable: {quant_output.score_matrix.most_likely_score} ({quant_output.score_matrix.most_likely_prob:.1%})")
    print(f"  Confianza del modelo: {quant_output.confidence_score}/100")
    
    # Análisis de Goles
    if tactical_output.goals_narrative:
        print("\n" + "-" * 80)
        print("⚽ ANÁLISIS DE GOLES (Over/Under 2.5)")
        print("-" * 80)
        gn = tactical_output.goals_narrative
        print(f"\n  📌 Recomendación: {gn.recommendation}")
        print(f"  📊 Probabilidad: {gn.our_probability:.1%}")
        print(f"  🎯 Signal Strength: {gn.signal_strength.value.upper()}")
        
        print(f"\n  ✅ PROS ({len(gn.pros)}):")
        for i, pro in enumerate(gn.pros, 1):
            print(f"     {i}. [{pro.weight.upper()}] {pro.factor}: {pro.description}")
        
        print(f"\n  ❌ CONTRAS ({len(gn.cons)}):")
        for i, con in enumerate(gn.cons, 1):
            print(f"     {i}. [{con.weight.upper()}] {con.factor}: {con.description}")
        
        print(f"\n  ⚠️  Riesgo Principal: {gn.key_risk}")
        print(f"\n  📝 Resumen: {gn.tactical_summary}")
    
    # Análisis de Tarjetas
    if tactical_output.cards_narrative:
        print("\n" + "-" * 80)
        print("🟨 ANÁLISIS DE TARJETAS")
        print("-" * 80)
        cn = tactical_output.cards_narrative
        print(f"\n  📌 Recomendación: {cn.recommendation}")
        print(f"  📊 Probabilidad: {cn.our_probability:.1%}")
        print(f"  🎯 Signal Strength: {cn.signal_strength.value.upper()}")
        
        print(f"\n  ✅ PROS ({len(cn.pros)}):")
        for i, pro in enumerate(cn.pros, 1):
            print(f"     {i}. [{pro.weight.upper()}] {pro.factor}: {pro.description}")
        
        print(f"\n  ❌ CONTRAS ({len(cn.cons)}):")
        for i, con in enumerate(cn.cons, 1):
            print(f"     {i}. [{con.weight.upper()}] {con.factor}: {con.description}")
        
        print(f"\n  ⚠️  Riesgo Principal: {cn.key_risk}")
        print(f"\n  📝 Resumen: {cn.tactical_summary}")
    
    # Análisis de Córneres
    if tactical_output.corners_narrative:
        print("\n" + "-" * 80)
        print("🚩 ANÁLISIS DE CÓRNERES")
        print("-" * 80)
        cn = tactical_output.corners_narrative
        print(f"\n  📌 Recomendación: {cn.recommendation}")
        print(f"  📊 Probabilidad: {cn.our_probability:.1%}")
        print(f"  🎯 Signal Strength: {cn.signal_strength.value.upper()}")
        
        print(f"\n  ✅ PROS ({len(cn.pros)}):")
        for i, pro in enumerate(cn.pros, 1):
            print(f"     {i}. [{pro.weight.upper()}] {pro.factor}: {pro.description}")
        
        print(f"\n  ❌ CONTRAS ({len(cn.cons)}):")
        for i, con in enumerate(cn.cons, 1):
            print(f"     {i}. [{con.weight.upper()}] {con.factor}: {con.description}")
        
        print(f"\n  ⚠️  Riesgo Principal: {cn.key_risk}")
        print(f"\n  📝 Resumen: {cn.tactical_summary}")
    
    # Bet Builder
    if tactical_output.bet_builder_suggestions:
        print("\n" + "-" * 80)
        print("🎯 BET BUILDER — COMBINADAS SUGERIDAS")
        print("-" * 80)
        
        for i, combo in enumerate(tactical_output.bet_builder_suggestions, 1):
            print(f"\n  {i}. {combo.name}")
            print(f"     🎲 Risk Level: {combo.risk_level.upper()}")
            print(f"     📊 Probabilidad Combinada: {combo.combined_probability:.1%}")
            if combo.combined_odds_estimate:
                print(f"     💰 Cuota Estimada: {combo.combined_odds_estimate:.2f}")
            
            print(f"\n     Legs:")
            for j, leg in enumerate(combo.legs, 1):
                print(f"        {j}. {leg}")
            
            print(f"\n     🔗 Correlación: {combo.correlation_rationale}")
    
    print("\n" + "=" * 80)
    print("✅ ANÁLISIS COMPLETADO EXITOSAMENTE")
    print("=" * 80 + "\n")


async def main():
    """Ejecuta la prueba de integración end-to-end."""
    
    # Cargar API key
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("❌ ERROR: GROQ_API_KEY no encontrada en .env")
        return False
    
    print("\n" + "=" * 80)
    print("🧪 PRUEBA DE INTEGRACIÓN END-TO-END: Cerebro Táctico + Groq API")
    print("=" * 80)
    print(f"\n📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 API Key: {groq_api_key[:10]}...{groq_api_key[-4:]}")
    
    # Paso 1: Diagnóstico de modelos
    if not list_groq_models(groq_api_key):
        return False
    
    # Paso 2: Construir datos mock
    print("\n📦 Construyendo datos mock del partido...")
    mock_data = build_mock_data()
    print(f"   ✅ Partido: {mock_data['home_team_name']} vs {mock_data['away_team_name']}")
    print(f"   ✅ Liga: {mock_data['league_name']}")
    print(f"   ✅ Árbitro: {mock_data['referee'].referee_name} ({mock_data['referee'].avg_yellow_cards} amarillas/partido)")
    print(f"   ✅ Contexto: Derby (rivalidad {mock_data['context'].rivalry_intensity}/5)")
    
    # Paso 3: Ejecutar pipeline completo
    print("\n🚀 Ejecutando pipeline completo (Fase 3 + Fase 4)...")
    print("   ⏳ Esto puede tomar 5-10 segundos...\n")
    
    start_time = time.time()
    
    try:
        quant_output, tactical_output = await run_full_analysis(
            **mock_data,
            groq_api_key=groq_api_key,
        )
        
        elapsed_time = time.time() - start_time
        
        # Paso 4: Imprimir resultados
        print_results(quant_output, tactical_output, elapsed_time)
        
        return True
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n❌ ERROR durante la ejecución ({elapsed_time:.2f}s):")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
