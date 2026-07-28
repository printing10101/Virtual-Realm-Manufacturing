"""探测 ProactorEventLoop 是否能绕过 WinSock 损坏导致的 socketpair 失败。"""
import asyncio
import sys

print(f"Python: {sys.version}")
print(f"Default policy: {asyncio.get_event_loop_policy().__class__.__name__}")

# 强制使用 ProactorEventLoopPolicy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print(f"Switched to: {asyncio.get_event_loop_policy().__class__.__name__}")

# 尝试创建事件循环
try:
    loop = asyncio.new_event_loop()
    print(f"Event loop created: {loop.__class__.__name__}")

    # 尝试运行一个简单协程
    async def hello():
        await asyncio.sleep(0.001)
        return "ok"

    result = loop.run_until_complete(hello())
    print(f"Coroutine result: {result}")
    loop.close()
    print("ProactorEventLoop 可用")
except OSError as e:
    print(f"FAILED: {e}")
    sys.exit(1)

# 现在尝试用 TestClient
print("\n--- 测试 TestClient ---")
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    client = TestClient(app)
    resp = client.get("/health")
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.json()}")
    print("TestClient 可用")
except OSError as e:
    print(f"FAILED: {e}")
    sys.exit(1)
