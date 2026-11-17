from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pymongo.errors import PyMongoError
from src.application import Application
from src.settings import Settings, load_config
from src.utils.logger import configure_logging


def create_app(application=None):
    configure_logging()

    @asynccontextmanager
    async def lifespan(app):
        try:
            await run_in_threadpool(app.state.services.initialize)
        except Exception:
            logging.getLogger('krishi').warning('MongoDB unavailable; API will retry on subsequent requests.')
        try:
            yield
        finally:
            await run_in_threadpool(app.state.services.close)

    app = FastAPI(title='Krishi Mitra', version='1.0.0', lifespan=lifespan)

    @app.get('/', include_in_schema=False)
    def backend_home():
        return RedirectResponse(url='/docs')

    app.state.services = application or Application(Settings(), load_config())
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                       allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type'])

    @app.exception_handler(PyMongoError)
    async def database_error(request, error):
        return JSONResponse(status_code=503, content={'detail': 'MongoDB is unavailable. Check the local database service.'})

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        logging.getLogger('krishi').error('request_failed type=%s', type(error).__name__)
        return JSONResponse(status_code=500, content={'detail': 'The operation failed. Check local storage, model downloads, and backend logs.'})
    from src.api.routes import router
    app.include_router(router, prefix='/api')
    return app


app = create_app()
