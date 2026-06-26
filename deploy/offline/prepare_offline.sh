#!/usr/bin/env bash
# =============================================================================
# 灵境制造 - Linux 离线包准备脚本
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[√]${NC} $*"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $*"; }
error() { echo -e "${RED}[错误]${NC} $*"; exit 1; }

echo "========================================"
echo " 灵境制造 - Linux 离线包准备脚本"
echo "========================================"
echo

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# 检查 Python
echo "[1/5] 检查 Python 环境..."
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    error "未检测到 Python"
fi
info "Python 环境正常: $($PYTHON_CMD --version)"

# 创建离线包目录
echo
echo "[2/5] 创建离线包目录结构..."
OFFLINE_DIR="$PROJECT_ROOT/deploy/offline/offline_package"
rm -rf "$OFFLINE_DIR"
mkdir -p "$OFFLINE_DIR"/{wheels,python,config,scripts,nginx}
info "目录结构创建完成"

# 下载 pip 依赖
echo
echo "[3/5] 下载 Python 依赖包（wheel 格式）..."
echo " 这可能需要几分钟，请耐心等待..."

# 先尝试下载当前平台的 wheel
pip download -r requirements.txt -d "$OFFLINE_DIR/wheels" \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    2>/dev/null || {
    warn "部分包下载失败，尝试补充下载..."
    pip download -r requirements.txt -d "$OFFLINE_DIR/wheels" \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-binary=:all: 2>/dev/null || true
}
info "依赖包下载完成"

# 下载 Docker 镜像（如果 Docker 可用）
echo
echo "[4/5] 保存 Docker 镜像..."
if command -v docker &>/dev/null; then
    # 构建镜像
    warn "尝试构建 Docker 镜像（可能需要较长时间）..."
    docker build -t lingjing-manufacturing:latest . 2>/dev/null && {
        mkdir -p "$OFFLINE_DIR/docker_images"
        docker save lingjing-manufacturing:latest -o "$OFFLINE_DIR/docker_images/lingjing-manufacturing.tar"
        info "Docker 镜像已保存"
    } || {
        warn "Docker 镜像构建失败，跳过（离线部署时将使用直接运行模式）"
    }

    # 保存依赖的公共镜像
    for img in redis:7-alpine postgres:16-alpine; do
        if docker image inspect "$img" &>/dev/null; then
            SAFE_NAME=$(echo "$img" | tr '/:' '_')
            docker save "$img" -o "$OFFLINE_DIR/docker_images/${SAFE_NAME}.tar"
            info "镜像 $img 已保存"
        fi
    done
else
    warn "未检测到 Docker，跳过镜像保存"
fi

# 复制项目文件
echo
echo "[5/5] 复制项目文件..."
cp -r "$PROJECT_ROOT/python/app" "$OFFLINE_DIR/python/"
cp "$PROJECT_ROOT/requirements.txt" "$OFFLINE_DIR/"
cp "$PROJECT_ROOT/.env.example" "$OFFLINE_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/docker-compose.yml" "$OFFLINE_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/docker-compose-cn.yml" "$OFFLINE_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/docker-compose-sqlite.yml" "$OFFLINE_DIR/" 2>/dev/null || true
cp -r "$PROJECT_ROOT/config/"* "$OFFLINE_DIR/config/" 2>/dev/null || true
cp -r "$PROJECT_ROOT/deploy/nginx/"* "$OFFLINE_DIR/nginx/" 2>/dev/null || true

# 复制离线安装脚本
cp "$SCRIPT_DIR/install_offline.sh" "$OFFLINE_DIR/"
cp "$SCRIPT_DIR/install_offline.bat" "$OFFLINE_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/README.md" "$OFFLINE_DIR/" 2>/dev/null || true

# 设置可执行权限
chmod +x "$OFFLINE_DIR/install_offline.sh" 2>/dev/null || true

info "项目文件复制完成"

# 打包
echo
echo "========================================"
echo " 离线包准备完成！"
echo "========================================"
echo
echo " 离线包位置: $OFFLINE_DIR"
echo
echo " 下一步操作："
echo "   1. 打包: tar -czf lingjing_offline_package.tar.gz -C $(dirname $OFFLINE_DIR) $(basename $OFFLINE_DIR)"
echo "   2. 传输到目标机器"
echo "   3. 解压: tar -xzf lingjing_offline_package.tar.gz"
echo "   4. 运行: cd offline_package && bash install_offline.sh"
echo

read -rp "是否现在打包? [y/N]: " ZIP_NOW
if [[ "$ZIP_NOW" =~ ^[Yy]$ ]]; then
    echo "正在打包..."
    tar -czf "$PROJECT_ROOT/deploy/offline/lingjing_offline_package.tar.gz" \
        -C "$(dirname "$OFFLINE_DIR")" "$(basename "$OFFLINE_DIR")"
    info "打包完成: deploy/offline/lingjing_offline_package.tar.gz"
fi
