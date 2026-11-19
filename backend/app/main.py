from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.router import api_router
from app.core.config import Settings
from app.database import initialize_database
from app.modules.monitoring.service import MonitorService


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if settings is None:
            application.state.settings = Settings()
        else:
            application.state.settings = settings
        initialize_database(application.state.settings.database_path)
        application.state.monitor = MonitorService(application.state.settings)
        await application.state.monitor.start()
        try:
            yield
        finally:
            await application.state.monitor.stop()

    application = FastAPI(
        title="Pingcheck API",
        description="Pingcheck 网络检测管理平台接口",
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(api_router)
    return application


app = create_app()
