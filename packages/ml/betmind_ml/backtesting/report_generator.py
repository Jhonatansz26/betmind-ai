"""
SRP: Genera el reporte final de backtesting en formato legible y serializable.
"""
from betmind_ml.backtesting.metrics import (
    BacktestReport,
    generate_full_report,
)
from betmind_ml.backtesting.simulator import BacktestPrediction

__all__ = [
    "BacktestReport",
    "generate_full_report",
    "format_report_as_text",
]


def format_report_as_text(report: BacktestReport) -> str:
    """
    Convierte un BacktestReport en un string formateado para logs o CLI.
    """
    return "\n".join(report.summary_lines)
