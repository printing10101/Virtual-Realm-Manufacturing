# =============================================================================
# Multi-stage Dockerfile for LNN Manufacturing AI Service
# 国内部署优化版 - 使用阿里云/华为云镜像源
# =============================================================================

# ---- Stage 1: Builder - 安装构建依赖和编译 Python 包 ----
# 国内镜像：使用华为云公共镜像仓库（也可替换为阿里云 ACR 地址）
FROM swr.cn-north-4.myhuaweicloud.com/library/python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /build

# 配置 pip 使用阿里云镜像源（国内必选）
RUN mkdir -p /etc/pip && \
    echo "[global]" > /etc/pip/pip.conf && \
    echo "index-url = https://mirrors.aliyun.com/pypi/simple/" >> /etc/pip/pip.conf && \
    echo "[install]" >> /etc/pip/pip.conf && \
    echo "trusted-host=mirrors.aliyun.com" >> /etc/pip/pip.conf

# 安装构建工具（仅在此阶段需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，充分利用 Docker 缓存层
COPY requirements.txt ./

# 安装 Python 依赖到独立目录（使用阿里云镜像源）
RUN pip install --no-cache-dir --prefix=/install \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt

# 复制源代码
COPY . .

# ---- Stage 2: Runtime - 最小化运行时镜像（国内镜像） ----
FROM swr.cn-north-4.myhuaweicloud.com/library/python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    APP_HOME=/app \
    APP_ENV=production \
    PORT=8765 \
    PYTHONPATH=/app/python

WORKDIR $APP_HOME

# 仅安装运行时依赖（最小化镜像体积）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# 从 builder 阶段复制已安装的 Python 包
COPY --from=builder /install /usr/local

# 复制应用代码（仅复制必要的目录）
COPY --from=builder /build/python/app ./python/app
COPY --from=builder /build/python/alembic ./python/alembic
COPY --from=builder /build/python/alembic.ini ./python/
COPY --from=builder /build/python/config ./python/config
COPY --from=builder /build/config ./config

# 创建非 root 用户并设置权限
RUN groupadd -r appuser && \
    useradd -r -g appuser -d $APP_HOME -s /sbin/nologin appuser && \
    chown -R appuser:appuser $APP_HOME

USER appuser

EXPOSE 8765

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8765/api/health/ping || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "4"]
