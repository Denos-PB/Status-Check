import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as web_router
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, init_db, seed_if_empty

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as session:
        try:
            await seed_if_empty(session)
            await session.commit()
        except Exception:
            await session.rollback()
            logging.exception("Database seed failed")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    @app.exception_handler(HTTPException)
    async def auth_redirect_handler(request: Request, exc: HTTPException):
        if exc.status_code == 401:
            return RedirectResponse(url="/login", status_code=302)
        return await http_exception_handler(request, exc)

    return app


app = create_app()
