import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.agents import router as ai_router
from app.ai.agents import router_chat as ai_chat_router
from app.ai.ollama_routes import router as ollama_router
from app.ai.workflow_routes import router as workflow_router
from app.api.batch import router as batch_router
from app.api.common.version import APIVersionMiddleware
from app.api.sse_router import router as sse_router
from app.api.v1.backup import router as backup_router
from app.api.v1.comparisons import router as comparisons_router
from app.api.v1.documents import router as documents_router
from app.api.v1.experiences import router as experiences_router
from app.api.v1.ground_truth import router as ground_truth_router
from app.api.v1.models import router as models_router
from app.api.v1.reports import router as reports_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.traces import router as traces_router
from app.api.v1.validation import router as validation_router
from app.api.v1.wear_prediction import router as wear_prediction_router
from app.api.v2 import router as v2_router
from app.cad.generator import router as cad_router
from app.cad.process_router import router as process_router
from app.config import config
from app.core.container import container
from app.core.input_validator import InputValidationMiddleware
from app.core.response import success
from app.models.schemas import AIStatusResponse, HealthResponse
from app.rag.routes import router as knowledge_router

logger = logging.getLogger(__name__)


def _get_cors_origins() -> list[str]:
    """
    根据环境变量动态获取CORS允许的来源列表

    安全考量:
    - 生产环境: 仅允许特定的来源(tauri://localhost和http://localhost)，防止跨站攻击
    - 开发环境: 允许localhost的多个端口，便于本地开发和调试
    - 所有环境均不使用通配符"*"，确保严格的来源验证
    """
    environment = config.environment.environment

    if environment == "production":
        allowed_origins = ["tauri://localhost", "http://localhost"]
    elif environment == "development":
        allowed_origins = [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "http://localhost:8765",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8765",
        ]
    else:
        logger.warning(
            f"[{environment}] 未知环境类型，使用开发环境CORS配置"
        )
        allowed_origins = [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "http://localhost:8765",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8765",
        ]

    return allowed_origins


def _log_cors_config(origins: list[str]) -> None:
    """
    记录CORS配置信息到日志

    安全考量:
    - 记录当前环境和允许的来源列表，便于审计和调试
    - 在生产环境检测到宽松配置时触发高级别警告
    - 日志格式包含时间戳、日志级别和具体配置内容
    """
    import datetime

    environment = config.environment.environment
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info(
        f"[{timestamp}] [CORS配置] 环境={environment}, "
        f"允许来源={origins}"
    )

    if environment == "production" and ("*" in origins or len(origins) > 5):
        logger.warning(
            f"[{timestamp}] [安全警告] 生产环境检测到不安全的CORS配置: "
            f"来源列表包含通配符或过于宽松 ({origins})"
        )


def _validate_cors_config(origins: list[str]) -> None:
    """
    验证CORS配置的安全性

    安全考量:
    - 在应用启动阶段执行CORS配置安全检查
    - 拒绝任何包含通配符"*"的配置
    - 生产环境额外检测过度宽松的来源设置
    - 验证失败时抛出明确的异常，阻止应用启动

    Raises:
        ValueError: 当检测到不安全的CORS配置时抛出
    """
    environment = config.environment.environment

    if "*" in origins:
        raise ValueError(
            f"[{environment}] CORS配置不允许使用通配符'*'，"
            f"必须明确指定允许的来源列表"
        )

    if environment == "production":
        unsafe_patterns = ["*", "http://*", "https://*", "*://*"]
        for origin in origins:
            if origin in unsafe_patterns or origin.endswith("/*"):
                raise ValueError(
                    f"[生产环境] 检测到不安全的CORS来源配置: {origin}。"
                    f"生产环境必须明确指定具体的来源地址"
                )

    logger.info(
        f"[{environment}] CORS配置验证通过，"
        f"允许 {len(origins)} 个来源"
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description="灵境制造 AI 后端服务"
    )

    cors_origins = _get_cors_origins()
    _log_cors_config(cors_origins)
    _validate_cors_config(cors_origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=config.security.allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRF-Token",
        ],
    )

    app.add_middleware(
        InputValidationMiddleware,
        skip_paths=["/health", "/docs", "/openapi.json", "/redoc"],
        max_length=1000,
        enabled=True
    )

    container.initialize()

    app.include_router(ai_router)
    app.include_router(ai_chat_router)
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
    app.include_router(ground_truth_router)
    app.include_router(scenarios_router)
    app.include_router(models_router)
    app.include_router(comparisons_router)
    app.include_router(documents_router)
    app.include_router(wear_prediction_router)
    app.include_router(batch_router)
    app.include_router(backup_router)
    app.include_router(v2_router)

    app.add_middleware(APIVersionMiddleware)

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        ai_available = False
        try:
            import httpx
            if config.ai.mode == "local":
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(f"{config.ai.ollama_base_url}/api/tags")
                    ai_available = response.status_code == 200
            else:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(f"{config.ai.cloud_base_url}/health")
                    ai_available = response.status_code == 200
        except Exception:
            ai_available = False

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
