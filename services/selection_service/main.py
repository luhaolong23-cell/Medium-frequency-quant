from fastapi import FastAPI

from packages.shared.http import install_exception_handlers
from services.selection_service.app.api.router import router as selection_router

app = FastAPI(title="Selection Service", version="0.1.0")
install_exception_handlers(app)
app.include_router(selection_router)
