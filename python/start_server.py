"""启动后端服务的辅助脚本，设置必要的环境变量。

P0-5 修复：原本无条件覆盖 LNN_JWT_SECRET，会导致 .env 中已配置的密钥被
随机覆盖，跨进程 JWT 失效。改为条件设置——仅在环境变量未配置时生成。
"""
import os
import secrets
import sys


def main():
    # P0-5 修复：仅在 LNN_JWT_SECRET 未设置时生成临时密钥
    if not os.environ.get("LNN_JWT_SECRET"):
        os.environ["LNN_JWT_SECRET"] = secrets.token_urlsafe(32)
        print("[startup] LNN_JWT_SECRET 未配置，已生成临时密钥（重启后失效）")
        # P1-7 修复：不得打印密钥任何前缀到 stdout——日志收集系统可能
        # 持久化 stdout，导致密钥泄露。仅提示配置状态，不输出密钥内容。
        print("[startup] 警告：生产环境请在 .env 中固定 LNN_JWT_SECRET")
    else:
        print("[startup] LNN_JWT_SECRET 已从环境变量加载")

    # 切换到 python 目录
    python_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(python_dir)
    print(f"Working directory: {python_dir}")

    # 启动 uvicorn
    # P0-6 修复：host 从环境变量读取，默认 127.0.0.1（仅本机访问），
    # 避免误用此脚本时在所有网络接口暴露 API。生产对外部署应通过
    # 反向代理（nginx）或显式设置 SERVER_HOST=0.0.0.0。
    import uvicorn
    host = os.environ.get("SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("SERVER_PORT", "8765"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
