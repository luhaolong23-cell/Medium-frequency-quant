from fastapi import FastAPI

from packages.shared.http import install_exception_handlers
from services.regime_service.app.api.router import router as regime_router

app = FastAPI(title="Regime Service", version="0.1.0")
install_exception_handlers(app)
app.include_router(regime_router)
