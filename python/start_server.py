"""启动后端服务的辅助脚本，设置必要的环境变量"""
import os
import secrets
import sys

def main():
    # 设置 JWT 密钥
    os.environ["LNN_JWT_SECRET"] = secrets.token_urlsafe(32)
    print(f"JWT secret set: {os.environ['LNN_JWT_SECRET'][:10]}...")

    # 切换到 python 目录
    python_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(python_dir)
    print(f"Working directory: {python_dir}")

    # 启动 uvicorn
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8765, reload=False)

if __name__ == "__main__":
    main()
