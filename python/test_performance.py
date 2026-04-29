import httpx
import asyncio
import json
import time

BASE_URL = "http://localhost:8765"

async def performance_test():
    print("=" * 60)
    print("性能测试 - 系统响应时间评估")
    print("=" * 60)
    
    results = []
    
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 测试 1: 根路径响应时间
        print("\n测试 1: GET / 响应时间")
        start = time.time()
        response = await client.get("/")
        elapsed = (time.time() - start) * 1000
        print(f"响应时间: {elapsed:.2f} ms")
        print(f"状态码: {response.status_code}")
        results.append(("GET /", elapsed))
        
        # 测试 2: 健康检查响应时间
        print("\n测试 2: GET /health 响应时间")
        start = time.time()
        response = await client.get("/health")
        elapsed = (time.time() - start) * 1000
        print(f"响应时间: {elapsed:.2f} ms")
        print(f"状态码: {response.status_code}")
        results.append(("GET /health", elapsed))
        
        # 测试 3: AI 状态响应时间
        print("\n测试 3: GET /api/ai/status 响应时间")
        start = time.time()
        response = await client.get("/api/ai/status")
        elapsed = (time.time() - start) * 1000
        print(f"响应时间: {elapsed:.2f} ms")
        print(f"状态码: {response.status_code}")
        results.append(("GET /api/ai/status", elapsed))
        
        # 测试 4: AI 设置更新响应时间
        print("\n测试 4: PUT /api/ai/settings 响应时间")
        settings_request = {
            "mode": "rule",
            "timeout": 30
        }
        start = time.time()
        response = await client.put("/api/ai/settings", json=settings_request)
        elapsed = (time.time() - start) * 1000
        print(f"响应时间: {elapsed:.2f} ms")
        print(f"状态码: {response.status_code}")
        results.append(("PUT /api/ai/settings", elapsed))
        
        # 测试 5: CAD 占位功能响应时间
        print("\n测试 5: POST /api/cad/cadquery 响应时间")
        cadquery_request = {"params": "test"}
        start = time.time()
        response = await client.post("/api/cad/cadquery", json=cadquery_request)
        elapsed = (time.time() - start) * 1000
        print(f"响应时间: {elapsed:.2f} ms")
        print(f"状态码: {response.status_code}")
        results.append(("POST /api/cad/cadquery", elapsed))
        
        # 测试 6: 工艺路线响应时间
        print("\n测试 6: POST /api/process/route 响应时间")
        process_request = {"item": "螺栓 M10"}
        start = time.time()
        response = await client.post("/api/process/route", json=process_request)
        elapsed = (time.time() - start) * 1000
        print(f"响应时间: {elapsed:.2f} ms")
        print(f"状态码: {response.status_code}")
        results.append(("POST /api/process/route", elapsed))
    
    # 汇总性能结果
    print("\n" + "=" * 60)
    print("性能测试结果汇总:")
    print("=" * 60)
    for endpoint, elapsed in results:
        print(f"{endpoint:40s} {elapsed:8.2f} ms")
    
    avg_time = sum(elapsed for _, elapsed in results) / len(results)
    print(f"\n平均响应时间: {avg_time:.2f} ms")
    
    if avg_time < 100:
        print("性能评级: [优秀]")
    elif avg_time < 500:
        print("性能评级: [良好]")
    elif avg_time < 1000:
        print("性能评级: [可接受]")
    else:
        print("性能评级: [需要优化]")
    
    return results

if __name__ == "__main__":
    asyncio.run(performance_test())
