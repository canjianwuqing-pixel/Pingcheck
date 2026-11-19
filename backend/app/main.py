import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.router import api_router
from app.core.config import Settings
from app.database import initialize_database
from app.modules.monitoring.service import MonitorService
from app.modules.telegram.service import TelegramService


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if settings is None:
            application.state.settings = Settings()
        else:
            application.state.settings = settings
        initialize_database(application.state.settings.database_path)
        application.state.telegram = TelegramService(application.state.settings)
        try:
            application.state.telegram.sync_proxy_configuration()
        except (OSError, ValueError):
            logger.warning(
                "Shadowsocks runtime configuration could not be synchronized; "
                "monitoring will continue"
            )
        application.state.monitor = MonitorService(
            application.state.settings, application.state.telegram
        )
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
