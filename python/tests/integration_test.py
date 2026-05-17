"""
灵境制造 — 刀路仿真完整集成测试

测试覆盖:
 1. 服务健康检查
 2. 正常路径仿真请求 (5+点直线插补)
 3. 响应字段完整性验证 (collision_detected, simulation_result, collision_details)
 4. 碰撞检测验证 (切入工作台路径, collision_detected=true)
 5. 连续5次API调用稳定性
 6. 前端页面可访问性
 7. 仿真前后数据一致性
"""
import httpx
import json
import time
import sys
import os

BASE_API = "http://localhost:8001"
BASE_WEB = "http://localhost:1420"
PASSED = 0
FAILED = 0
RESULTS = []


def check(name, condition, detail=""):
    global PASSED, FAILED, RESULTS
    if condition:
        PASSED += 1
        RESULTS.append(f"  [PASS] {name}")
    else:
        FAILED += 1
        RESULTS.append(f"  [FAIL] {name}  {detail}")
    print(RESULTS[-1])


def section(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


# ================================================================
# SECTION 1: 服务健康检查
# ================================================================
section("1. 服务健康检查")

try:
    r = httpx.get(f"{BASE_API}/api/health", timeout=5)
    check("API服务 HTTP 200", r.status_code == 200, f"got {r.status_code}")
    check("API状态ok", r.json().get("status") == "ok")
except Exception as e:
    check("API服务可达", False, str(e))

try:
    r = httpx.get(f"{BASE_WEB}", timeout=5)
    check(f"前端页面 HTTP {r.status_code}", r.status_code in (200, 301, 302),
          f"got {r.status_code}")
except Exception as e:
    check("前端页面可达", False, str(e))


# ================================================================
# SECTION 2: 正常路径仿真 (5+点直线插补)
# ================================================================
section("2. 正常路径仿真请求 (6点直线插补)")

GCODE_NORMAL = """%
O0001
G21 G17 G90
G00 Z50.
G00 X0. Y0.
G01 Z5. F500
G01 X30. Y10. F800
G01 X50. Y25. F800
G01 X40. Y40. F800
G01 X10. Y35. F800
G01 X0. Y10. F800
G00 Z50.
M30
%"""

payload_normal = {
    "project_id": "integration_test_normal",
    "voxel_size": 2.0,
    "tool_diameter": 8.0,
    "tool_length": 40.0,
    "tool_type": "flat",
    "gcode": GCODE_NORMAL,
    "safe_z_height": 10.0,
    "stock_stl_path": "",
}

t0 = time.time()
resp = httpx.post(f"{BASE_API}/api/simulation/run", json=payload_normal, timeout=120)
elapsed = time.time() - t0

check("正常仿真 HTTP 200", resp.status_code == 200, f"got {resp.status_code}")
data = resp.json()
check("正常仿真 code=0", data.get("code") == 0, f"code={data.get('code')}")
check("响应时间 < 10s", elapsed < 10.0, f"{elapsed:.2f}s")

d = data.get("data", {})

# ---- 响应字段完整性 ----
check("[字段] collision_detected 存在", "collision_detected" in d)
check("[字段] collision_detected 布尔型", isinstance(d.get("collision_detected"), bool))
check("[字段] simulation_result 存在", "simulation_result" in d)
check("[字段] workpiece_stl_path 存在",
      "workpiece_stl_path" in d.get("simulation_result", {}))
check("[字段] workpiece_stl_path 非空",
      bool(d.get("simulation_result", {}).get("workpiece_stl_path")))
check("[字段] collision_details 存在", "collision_details" in d)
check("[字段] collision_details.timestamp",
      "timestamp" in d.get("collision_details", {}))
check("[字段] collision_details.positions",
      "positions" in d.get("collision_details", {}))
check("[字段] collision_details.severity",
      "severity" in d.get("collision_details", {}))
check("[字段] collision_details.count",
      isinstance(d.get("collision_details", {}).get("count"), int))
check("[字段] task_id 非空", len(d.get("task_id", "")) > 0)
check("[字段] duration_seconds > 0", d.get("duration_seconds", 0) > 0)
check("[字段] toolpath_segment_count >= 5",
      d.get("toolpath_segment_count", 0) >= 5,
      f"got {d.get('toolpath_segment_count')}")

# 安全路径不应该触发碰撞
normal_collision = d.get("collision_detected")
print(f"  [INFO] 安全路径 collision_detected={normal_collision}")


# ================================================================
# SECTION 3: 碰撞检测验证 (切入工作台)
# ================================================================
section("3. 碰撞检测验证 (切入工作台)")

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

payload_collision = {
    "project_id": "integration_test_collision",
    "voxel_size": 2.0,
    "tool_diameter": 8.0,
    "tool_length": 40.0,
    "tool_type": "flat",
    "gcode": GCODE_COLLISION,
    "safe_z_height": 10.0,
    "stock_stl_path": "",
}

resp2 = httpx.post(f"{BASE_API}/api/simulation/run",
                   json=payload_collision, timeout=120)
check("碰撞仿真 HTTP 200", resp2.status_code == 200)
check("碰撞仿真 code=0", resp2.json().get("code") == 0)

d2 = resp2.json().get("data", {})
check("collision_detected == true", d2.get("collision_detected") == True,
      f"got {d2.get('collision_detected')}")

cd = d2.get("collision_details", {})
check("collision_details.count > 0", cd.get("count", 0) > 0)
check("collision_details.severity 非空", cd.get("severity") != "none")
check("collision_details.timestamp 存在", bool(cd.get("timestamp")))

if cd.get("positions"):
    fp = cd["positions"][0]
    check("碰撞位置Z < 0 (切入工作台)", fp[2] < 0,
          f"Z={fp[2]:.2f}")
    print(f"  [INFO] 首个碰撞位置: ({fp[0]:.2f}, {fp[1]:.2f}, {fp[2]:.2f})")
    print(f"  [INFO] severity={cd.get('severity')}, count={cd.get('count')}")


# ================================================================
# SECTION 4: 连续5次API调用稳定性
# ================================================================
section("4. 连续5次API调用稳定性")

batch_results = []
for i in range(5):
    t_start = time.time()
    try:
        r = httpx.post(f"{BASE_API}/api/simulation/run",
                       json=payload_normal, timeout=60)
        t_end = time.time()
        ok = r.status_code == 200 and r.json().get("code") == 0
        batch_results.append({"i": i, "ok": ok, "t": t_end - t_start,
                              "tid": r.json().get("data", {}).get("task_id")})
        status = "OK" if ok else "FAIL"
        print(f"  #{i}: {status} | {t_end-t_start:.2f}s | task={batch_results[-1]['tid']}")
    except Exception as e:
        batch_results.append({"i": i, "ok": False, "t": 0, "tid": str(e)})
        print(f"  #{i}: ERROR - {e}")

all_passed = all(r["ok"] for r in batch_results)
check("5次连续请求全部成功", all_passed)
if batch_results:
    times = [r["t"] for r in batch_results if r["ok"]]
    if times:
        avg_time = sum(times) / len(times)
        check(f"平均响应时间 < 10s", avg_time < 10,
              f"avg={avg_time:.2f}s")


# ================================================================
# SECTION 5: 仿真结果数据一致性
# ================================================================
section("5. 数据一致性验证")

check("task_id 不同 (不同请求)", d.get("task_id") != d2.get("task_id"),
      f"{d.get('task_id')} vs {d2.get('task_id')}")

check("voxel_count > 0 (正常)", d.get("voxel_count", 0) > 0)
check("voxel_count > 0 (碰撞)", d2.get("voxel_count", 0) > 0)

check("正常路径 removed > 0 (有切削)", d.get("removed_voxel_count", 0) > 0,
      f"removed={d.get('removed_voxel_count')}")

# ================================================================
# SECTION 6: 状态查询端点
# ================================================================
section("6. 任务状态查询")

task_id = d.get("task_id")
resp3 = httpx.get(f"{BASE_API}/api/simulation/status/{task_id}", timeout=10)
check("Status HTTP 200", resp3.status_code == 200)
sdata = resp3.json().get("data", {})
check("status=completed", sdata.get("status") == "completed")
check("progress=1.0", sdata.get("progress") == 1.0)
check("result 非空", sdata.get("result") is not None)

# 验证 status 端点中的碰撞字段
if sdata.get("result"):
    sr = sdata["result"]
    check("status result 含 collision_detected",
          "collision_detected" in sr)
    check("status result 含 simulation_result",
          "simulation_result" in sr)

# ================================================================
# SECTION 7: 错误处理
# ================================================================
section("7. 错误处理验证")

# 无效的voxel_size
payload_bad = {**payload_normal, "voxel_size": 100.0}
resp_bad = httpx.post(f"{BASE_API}/api/simulation/run",
                      json=payload_bad, timeout=30)
# Pydantic 会拒绝超过范围的值 (ge=0.1, le=10.0)
check("无效参数返回 422", resp_bad.status_code == 422,
      f"got {resp_bad.status_code}")

# 空G代码
payload_empty = {**payload_normal, "gcode": ""}
resp_empty = httpx.post(f"{BASE_API}/api/simulation/run",
                        json=payload_empty, timeout=60)
check("空G代码 HTTP 200", resp_empty.status_code == 200)
edata = resp_empty.json().get("data", {})
check("空G代码 segment_count=0", edata.get("toolpath_segment_count", -1) == 0,
      f"got {edata.get('toolpath_segment_count')}")


# ================================================================
# SUMMARY
# ================================================================
section("测试汇总")
total = PASSED + FAILED
status_text = "ALL PASSED" if FAILED == 0 else "SOME FAILED"
print(f"  {status_text} | {PASSED} passed, {FAILED} failed, {total} total")

if FAILED > 0:
    print("\n  失败项:")
    for r in RESULTS:
        if "[FAIL]" in r:
            print(f"   {r}")

sys.exit(0 if FAILED == 0 else 1)
