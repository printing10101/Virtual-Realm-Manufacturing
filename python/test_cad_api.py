import asyncio
import httpx
from pathlib import Path


async def test_cad_query_api():
    base_url = "http://127.0.0.1:8765"
    
    print("===== 测试 1: CadQuery 生成 API =====")
    
    script = """import cadquery as cq

shape = cq.Workplane("XY").box(50, 50, 30)
shape = shape.faces(">Z").workplane().center(0, 0).hole(10)

import sys
output_path = sys.argv[1] if len(sys.argv) > 1 else 'output.stl'
export_format = sys.argv[2] if len(sys.argv) > 2 else 'stl'

from cadquery import exporters
if export_format.lower() == 'stl':
    exporters.export(shape, output_path)
"""
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{base_url}/api/cad/cadquery",
            json={
                "script": script,
                "output_format": "stl"
            }
        )
        
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {data}")
        
        if data.get('code') == 0:
            task_id = data['data']['task_id']
            print(f"任务创建成功，Task ID: {task_id}")
            
            print("\n等待 10 秒让任务完成...")
            await asyncio.sleep(10)
            
            print("\n查询任务状态...")
            status_resp = await client.get(f"{base_url}/api/cad/tasks/{task_id}")
            status_data = status_resp.json()
            print(f"任务状态: {status_data}")
            
            if status_data['data']['status'] == 'completed':
                print("[OK] CadQuery generation successful!")
            else:
                print("[FAIL] CadQuery generation failed or not yet complete")
        else:
            print(f"[FAIL] API call failed: {data.get('message')}")


async def test_health():
    print("===== 测试 0: 健康检查 =====")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("http://127.0.0.1:8765/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")


async def main():
    await test_health()
    await asyncio.sleep(1)
    await test_cad_query_api()


if __name__ == "__main__":
    asyncio.run(main())
