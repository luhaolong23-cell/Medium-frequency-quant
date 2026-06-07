from fastapi import FastAPI

from packages.shared.http import install_exception_handlers
from services.refdata_service.app.api.router import router as refdata_router

app = FastAPI(title="Refdata Service", version="0.1.0")
install_exception_handlers(app)
app.include_router(refdata_router)
