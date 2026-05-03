import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.config import config
from app.core.response import success, error, ErrorCode
from app.core.exceptions import app_exception_handler, general_exception_handler, AppException
from app.core.exception_handler import (
    validation_exception_handler,
    pydantic_validation_exception_handler
)
from app.core.container import container
from app.models.schemas import HealthResponse, AIStatusResponse, AIMode
from app.ai.llm_client import get_llm_client

from app.ai.agents import router as ai_router
from app.ai.ollama_routes import router as ollama_router
from app.ai.workflow_routes import router as workflow_router
from app.cad.generator import router as cad_router
from app.cad.process_router import router as process_router
from app.rag.routes import router as knowledge_router
from app.api.sse_router import router as sse_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.reports import router as reports_router
from app.api.v1.validation import router as validation_router
from app.api.v1.traces import router as traces_router
from app.api.v1.experiences import router as experiences_router
from app.api.v1.scenarios import router as scenarios_router


def create_app() -> FastAPI:
    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description="灵境制造 AI 后端服务"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.security.cors_origins if config.security.cors_origins != ["*"] else ["*"],
        allow_credentials=config.security.allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)

    container.initialize()

    app.include_router(ai_router)
    app.include_router(ollama_router)
    app.include_router(workflow_router)
    app.include_router(cad_router)
    app.include_router(process_router)
    app.include_router(knowledge_router)
    app.include_router(sse_router)
    app.include_router(tasks_router)
    app.include_router(reports_router)
    app.include_router(validation_router)
    app.include_router(traces_router)
    app.include_router(experiences_router)
    app.include_router(scenarios_router)

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        ai_client = get_llm_client()
        ai_available = await ai_client.is_available()

        ai_status = AIStatusResponse(
            mode=config.ai.mode,
            available=ai_available,
            model=config.ai.ollama_model if config.ai.mode == "local" else config.ai.cloud_model
        )

        return HealthResponse(
            status="healthy" if ai_available else "degraded",
            version=config.app_version,
            ai_status=ai_status
        )

    @app.get("/")
    async def root():
        return success(data={
            "app": config.app_name,
            "version": config.app_version,
            "docs": "/docs"
        })

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug
    )
