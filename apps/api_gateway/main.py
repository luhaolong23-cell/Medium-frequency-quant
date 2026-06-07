from fastapi import FastAPI

from apps.api_gateway.routes.agent import router as agent_router
from apps.api_gateway.routes.admin import router as admin_router
from apps.api_gateway.routes.candidates import router as candidates_router
from apps.api_gateway.routes.data_sources import router as data_sources_router
from apps.api_gateway.routes.health import router as health_router
from apps.api_gateway.routes.markets import router as markets_router
from apps.api_gateway.routes.orders import router as orders_router
from apps.api_gateway.routes.positions import router as positions_router
from apps.api_gateway.routes.seeds import router as seeds_router
from apps.api_gateway.routes.signals import router as signals_router
from apps.api_gateway.routes.themes import router as themes_router
from apps.api_gateway.routes.universe import router as universe_router
from apps.api_gateway.routes.watchlist import router as watchlist_router
from apps.api_gateway.routes.workflow import router as workflow_router
from packages.shared.http import install_exception_handlers

app = FastAPI(
    title='Quant Platform API Gateway',
    version='0.1.0',
    description='Gateway for market-regime orchestration, daily stock ranking, and paper-trading queries.',
)

install_exception_handlers(app)
app.include_router(health_router)
app.include_router(admin_router)
app.include_router(markets_router)
app.include_router(candidates_router)
app.include_router(watchlist_router)
app.include_router(themes_router)
app.include_router(universe_router)
app.include_router(seeds_router)
app.include_router(workflow_router)
app.include_router(signals_router)
app.include_router(orders_router)
app.include_router(positions_router)
app.include_router(data_sources_router)

app.include_router(agent_router)
