"""仿真API完整测试脚本。"""
import httpx
import json
import os
import sys

BASE = "http://localhost:8001"
PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name}  {detail}")


# ============================================================
# TEST 1: Health Check
# ============================================================
print("=" * 60)
print("TEST 1: 服务健康检查")
print("=" * 60)
r = httpx.get(f"{BASE}/api/health", timeout=5)
check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
check("status=ok", r.json().get("status") == "ok", r.text)
check("ping", httpx.get(f"{BASE}/api/health/ping").json().get("ping") == True)

# ============================================================
# TEST 2: Normal Simulation - 5+ point linear toolpath
# ============================================================
print()
print("=" * 60)
print("TEST 2: 正常路径仿真请求 (6点直线插补)")
print("=" * 60)

GCODE_NORMAL = """%
O0001
G21 G17 G90
G00 Z50.
G00 X0. Y0. Z50.
G01 Z5. F500
G01 X30. Y10. F800
G01 X50. Y25. F800
G01 X40. Y40. F800
G01 X10. Y35. F800
G01 X0. Y10. F800
G00 Z50.
M30
%"""

stock_path = os.path.abspath("output/simulation/test_stock.stl")

payload = {
    "project_id": "test_normal_001",
    "voxel_size": 2.0,
    "tool_diameter": 8.0,
    "tool_length": 40.0,
    "tool_type": "flat",
    "gcode": GCODE_NORMAL,
    "safe_z_height": 10.0,
    "stock_stl_path": stock_path,
}

resp = httpx.post(f"{BASE}/api/simulation/run", json=payload, timeout=120)
check("HTTP 200", resp.status_code == 200, f"got {resp.status_code}")

data = resp.json()
check("code=0", data.get("code") == 0, f"code={data.get('code')}")
check("message present", "message" in data)

d = data.get("data", {})

# --- 字段验证 ---
check("collision_detected 存在", "collision_detected" in d)
check("collision_detected 布尔类型", isinstance(d.get("collision_detected"), bool))
check("simulation_result 存在", "simulation_result" in d)
check("workpiece_stl_path 存在", "workpiece_stl_path" in d.get("simulation_result", {}))
check("workpiece_stl_path 非空", bool(d.get("simulation_result", {}).get("workpiece_stl_path")))
check("collision_details 存在", "collision_details" in d)
check("collision_details.timestamp 存在", "timestamp" in d.get("collision_details", {}))
check("collision_details.positions 存在", "positions" in d.get("collision_details", {}))
check("collision_details.severity 存在", "severity" in d.get("collision_details", {}))
check("collision_details.count 存在", "count" in d.get("collision_details", {}))
check("task_id 存在", "task_id" in d and len(d["task_id"]) > 0)
check("duration_seconds > 0", d.get("duration_seconds", 0) > 0)
check("toolpath_segment_count > 5", d.get("toolpath_segment_count", 0) >= 5,
      f"segments={d.get('toolpath_segment_count')}")

print()
print(f"  task_id: {d.get('task_id')}")
print(f"  collision_detected: {d.get('collision_detected')}")
print(f"  workpiece_stl_path: {d.get('simulation_result',{}).get('workpiece_stl_path')}")
print(f"  duration_seconds: {d.get('duration_seconds')}")
print(f"  collision_details.severity: {d.get('collision_details',{}).get('severity')}")
print(f"  collision_details.count: {d.get('collision_details',{}).get('count')}")
print(f"  voxel_count: {d.get('voxel_count')} / removed: {d.get('removed_voxel_count')}")

# ============================================================
# TEST 3: Collision Verification - Toolpath cuts into workbench
# ============================================================
print()
print("=" * 60)
print("TEST 3: 碰撞检测验证 (切入工作台的刀路)")
print("=" * 60)

GCODE_COLLISION = """%
O0002
G21 G17 G90
G00 Z80.
G00 X0. Y0.
G01 Z-15. F500
G01 X20. F800
G01 X40.
G01 X60.
G01 X80.
G01 Z-30. F500
G01 X60. F800
G01 X40.
G01 X20.
G01 X0.
G00 Z80.
M30
%"""

payload2 = {
    "project_id": "test_collision_001",
    "voxel_size": 2.0,
    "tool_diameter": 8.0,
    "tool_length": 40.0,
    "tool_type": "flat",
    "gcode": GCODE_COLLISION,
    "safe_z_height": 10.0,
    "stock_stl_path": stock_path,
}

resp2 = httpx.post(f"{BASE}/api/simulation/run", json=payload2, timeout=120)
check("碰撞 HTTP 200", resp2.status_code == 200, f"got {resp2.status_code}")

data2 = resp2.json()
d2 = data2.get("data", {})

check("碰撞 code=0", data2.get("code") == 0)
check("collision_detected == true", d2.get("collision_detected") == True,
      f"got {d2.get('collision_detected')}")
check("collision_details.count > 0", d2.get("collision_details", {}).get("count", 0) > 0)

cd = d2.get("collision_details", {})
print()
print(f"  collision_detected: {d2.get('collision_detected')}")
print(f"  collision_details.severity: {cd.get('severity')}")
print(f"  collision_details.count: {cd.get('count')}")
print(f"  collision_details.timestamp: {cd.get('timestamp')}")
if cd.get("positions"):
    print(f"  First collision position: ("
          f"{cd['positions'][0][0]:.2f}, "
          f"{cd['positions'][0][1]:.2f}, "
          f"{cd['positions'][0][2]:.2f})")
if cd.get("segment_indices"):
    print(f"  Collision segment indices: {cd.get('segment_indices')[:5]}")

# ============================================================
# TEST 4: Status endpoint
# ============================================================
print()
print("=" * 60)
print("TEST 4: 任务状态查询")
print("=" * 60)

task_id = d.get("task_id")
resp3 = httpx.get(f"{BASE}/api/simulation/status/{task_id}", timeout=10)
check("Status HTTP 200", resp3.status_code == 200)
data3 = resp3.json()
d3 = data3.get("data", {})
check("状态字段存在", "status" in d3)
check("status=completed", d3.get("status") == "completed", f"got {d3.get('status')}")
check("progress=1.0", d3.get("progress") == 1.0, f"got {d3.get('progress')}")
print(f"  status: {d3.get('status')}, progress: {d3.get('progress')}")

# ============================================================
# Summary
# ============================================================
print()
print("=" * 60)
print(f"测试汇总: {PASSED} 通过, {FAILED} 失败, {PASSED + FAILED} 总计")
print("=" * 60)

sys.exit(0 if FAILED == 0 else 1)
