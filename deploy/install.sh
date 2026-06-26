#!/usr/bin/env bash
# =============================================================================
# 灵境制造 - Linux/macOS 一键安装脚本
# =============================================================================
set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[√]${NC} $*"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $*"; }
error() { echo -e "${RED}[错误]${NC} $*"; }

echo "========================================"
echo " 灵境制造 - Linux/macOS 一键安装脚本"
echo "========================================"
echo

# 获取项目根目录（脚本所在目录的上级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ------------------------------------------------------------------
# [1/5] 检查 Python 版本
# ------------------------------------------------------------------
echo "[1/5] 检查 Python 环境..."

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    error "未检测到 Python，请先安装 Python 3.10 或更高版本"
    echo "  Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"
    echo "  CentOS/RHEL:   sudo yum install python3.11"
    echo "  macOS:         brew install python@3.11"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
info "检测到 Python $PYTHON_VERSION"

# 检查版本号 >= 3.10
MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
    error "Python 版本过低 ($PYTHON_VERSION)，需要 3.10 或更高版本"
    exit 1
fi

# ------------------------------------------------------------------
# [2/5] 创建虚拟环境
# ------------------------------------------------------------------
echo
echo "[2/5] 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    $PYTHON_CMD -m venv venv
    info "虚拟环境创建成功"
else
    info "虚拟环境已存在，跳过创建"
fi

# 激活虚拟环境
source venv/bin/activate

# ------------------------------------------------------------------
# [3/5] 安装依赖（阿里云镜像）
# ------------------------------------------------------------------
echo
echo "[3/5] 安装 Python 依赖（使用阿里云镜像）..."

pip install --upgrade pip \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com -q

pip install -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

if [ $? -ne 0 ]; then
    error "依赖安装失败"
    exit 1
fi
info "依赖安装完成"

# ------------------------------------------------------------------
# [4/5] 初始化数据库
# ------------------------------------------------------------------
echo
echo "[4/5] 初始化数据库..."
cd python
$PYTHON_CMD -c "
from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)
print('数据库初始化完成')
" 2>/dev/null && info "数据库初始化完成" || warn "数据库初始化失败，请检查 .env 文件中的数据库配置"
cd "$PROJECT_ROOT"

# ------------------------------------------------------------------
# [5/5] 检测 systemd 并创建服务文件
# ------------------------------------------------------------------
echo
echo "[5/5] 配置系统服务..."

if command -v systemctl &>/dev/null && [ -d /etc/systemd/system ]; then
    SERVICE_FILE="/etc/systemd/system/lingjing-manufacturing.service"
    cat > /tmp/lingjing-manufacturing.service <<EOF
[Unit]
Description=灵境制造 LNN Manufacturing AI Service
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$PROJECT_ROOT/python
Environment=PATH=$PROJECT_ROOT/venv/bin:/usr/local/bin:/usr/bin
ExecStart=$PROJECT_ROOT/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --log-level info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    echo "检测到 systemd，是否 to install the service file?"
    echo "  服务文件将写入: $SERVICE_FILE"
    echo "  需要 root 权限（将使用 sudo）"
    read -rp "是否安装系统服务? [y/N]: " INSTALL_SERVICE
    if [[ "$INSTALL_SERVICE" =~ ^[Yy]$ ]]; then
        sudo cp /tmp/lingjing-manufacturing.service "$SERVICE_FILE"
        sudo systemctl daemon-reload
        sudo systemctl enable lingjing-manufacturing.service
        info "系统服务已安装并设为开机自启"
        echo "  启动服务: sudo systemctl start lingjing-manufacturing"
        echo "  查看状态: sudo systemctl status lingjing-manufacturing"
    else
        info "跳过系统服务安装"
    fi
    rm -f /tmp/lingjing-manufacturing.service
else
    info "未检测到 systemd，跳过系统服务配置"
fi

# ------------------------------------------------------------------
# 启动提示
# ------------------------------------------------------------------
echo
echo "========================================"
echo " 安装完成！"
echo "========================================"
echo
echo " 启动方式："
echo "   手动启动:  cd $PROJECT_ROOT/python && ../venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8765"
echo "   服务地址:  http://localhost:8765"
echo "   API 文档:  http://localhost:8765/docs"
echo
echo " 提示: 运行 'source venv/bin/activate' 激活虚拟环境"
echo
