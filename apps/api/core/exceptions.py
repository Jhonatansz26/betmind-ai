# apps/api/core/exceptions.py
"""
Excepciones reservadas para errores de infraestructura (DB, APIs externas).
Los errores de dominio viajan como Err() dentro del Result pattern.
"""


class BetMindException(Exception):
    """Base exception de la aplicación."""
    pass


class MatchNotFoundException(BetMindException):
    def __init__(self, match_id: int):
        super().__init__(f"Partido con ID {match_id} no encontrado.")
        self.match_id = match_id


class PredictionNotAvailableException(BetMindException):
    def __init__(self, match_id: int):
        super().__init__(f"Sin datos suficientes para predecir el partido {match_id}.")
        self.match_id = match_id


class ExternalAPIException(BetMindException):
    def __init__(self, service: str, detail: str):
        super().__init__(f"Error en servicio externo '{service}': {detail}")
        self.service = service


class AccountSuspendedError(ExternalAPIException):
    """
    Cuenta suspendida o plan sin acceso al proveedor externo (ej. API-Football
    devuelve HTTP 200 con {'errors': {'access': 'Your account is suspended...'}}).

    Los callers deben tratarla como fallo DEFINITIVO de la fuente: no reintentar
    ni seguir iterando partidos contra el mismo proveedor en esta ejecución.
    """

    def __init__(self, service: str, detail: str = "Account suspended"):
        super().__init__(service=service, detail=detail)
        self.suspended = True