from fastapi import APIRouter

from apps.api.routes.v1 import auth, matches, predictions, scanner

api_router = APIRouter()

api_router.include_router(predictions.router)
api_router.include_router(matches.router, prefix="/matches", tags=["matches"])
api_router.include_router(scanner.router, prefix="/scanner", tags=["scanner"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
