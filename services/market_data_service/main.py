from fastapi import FastAPI

from packages.shared.http import install_exception_handlers
from services.market_data_service.app.api.router import router as market_data_router

app = FastAPI(title="Market Data Service", version="0.1.0")
install_exception_handlers(app)
app.include_router(market_data_router)
