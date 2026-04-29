import httpx
import asyncio
import json

BASE_URL = "http://localhost:8765"

async def test_all_endpoints():
    results = []
    
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 1. 测试根路径
        print("=" * 50)
        print("测试 1: GET /")
        response = await client.get("/")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        results.append(("GET /", response.status_code == 200))
        
        # 2. 测试健康检查
        print("\n" + "=" * 50)
        print("测试 2: GET /health")
        response = await client.get("/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        results.append(("GET /health", response.status_code == 200))
        
        # 3. 测试 AI 状态
        print("\n" + "=" * 50)
        print("测试 3: GET /api/ai/status")
        response = await client.get("/api/ai/status")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        results.append(("GET /api/ai/status", response.status_code == 200))
        
        # 4. 测试 AI 对话 (LLM 可能不可用，但应该返回正确响应格式)
        print("\n" + "=" * 50)
        print("测试 4: POST /api/ai/chat")
        chat_request = {
            "messages": [
                {"role": "user", "content": "你好"}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
            "stream": False
        }
        response = await client.post("/api/ai/chat", json=chat_request)
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        results.append(("POST /api/ai/chat", response.status_code == 200))
        
        # 5. 测试 AI 设置更新
        print("\n" + "=" * 50)
        print("测试 5: PUT /api/ai/settings")
        settings_request = {
            "mode": "rule",
            "timeout": 30
        }
        response = await client.put("/api/ai/settings", json=settings_request)
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        results.append(("PUT /api/ai/settings", response.status_code == 200))
        
        # 6. 测试 CAD 三视图生成 (占位功能，应该返回错误)
        print("\n" + "=" * 50)
        print("测试 6: POST /api/cad/three-view-to-3d")
        cad_request = {"view_data": "test"}
        response = await client.post("/api/cad/three-view-to-3d", json=cad_request)
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        # 这个应该返回错误，所以 200 但 code != 0
        results.append(("POST /api/cad/three-view-to-3d", response.status_code == 200))
        
        # 7. 测试 CAD CadQuery 生成
        print("\n" + "=" * 50)
        print("测试 7: POST /api/cad/cadquery")
        cadquery_request = {"params": "test"}
        response = await client.post("/api/cad/cadquery", json=cadquery_request)
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        results.append(("POST /api/cad/cadquery", response.status_code == 200))
        
        # 8. 测试工艺路线生成
        print("\n" + "=" * 50)
        print("测试 8: POST /api/process/route")
        process_request = {"item": "螺栓 M10"}
        response = await client.post("/api/process/route", json=process_request)
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        results.append(("POST /api/process/route", response.status_code == 200))
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    for endpoint, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} - {endpoint}")
    print(f"\n总计: {passed}/{total} 通过")
    return passed == total

if __name__ == "__main__":
    result = asyncio.run(test_all_endpoints())
    if result:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed, please check the output above.")
