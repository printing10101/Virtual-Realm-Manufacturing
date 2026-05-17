"""仿真模块独立测试服务器。

仅加载仿真API路由，不依赖项目中其他可能存在导入问题的模块。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.simulation.api import router as simulation_router
from app.projects.project_api import router as project_router

app = FastAPI(
    title="灵境制造 - 集成测试",
    version="1.9.0-test",
    docs_url="/api/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulation_router)
app.include_router(project_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "simulation-test"}


@app.get("/api/health/ping")
async def ping():
    return {"ping": True}
