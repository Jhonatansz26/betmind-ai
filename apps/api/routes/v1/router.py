from fastapi import APIRouter

from apps.api.routes.v1 import auth, bankroll, matches, predictions, scanner, backtesting, tickets, leagues, users, subscriptions

api_router = APIRouter()

api_router.include_router(predictions.router)
api_router.include_router(matches.router, prefix="/matches", tags=["matches"])
api_router.include_router(scanner.router, prefix="/scanner", tags=["scanner"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(bankroll.router, prefix="/bankroll", tags=["bankroll"])
api_router.include_router(backtesting.router)
api_router.include_router(tickets.router)
api_router.include_router(leagues.router)
api_router.include_router(subscriptions.router)
api_router.include_router(subscriptions.webhook_router)
