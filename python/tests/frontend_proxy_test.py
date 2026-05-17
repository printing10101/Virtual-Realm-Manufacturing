"""前端代理测试 - 通过Vite Proxy验证前后端联通"""
import httpx
import sys

BASE = "http://localhost:1420"
passed = 0
failed = 0

def chk(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")

# 1. 主页HTML
r = httpx.get(BASE, timeout=10)
chk("首页 HTTP 200", r.status_code == 200)
chk("首页HTML包含app容器", "app" in r.text.lower() or "div" in r.text)
print(f"  [INFO] 首页: {r.status_code}, {len(r.text)} bytes")

# 2. Workspace
r = httpx.get(f"{BASE}/workspace", timeout=10)
chk("Workspace HTTP 200", r.status_code == 200)
chk("Workspace SPA路由正常", len(r.text) > 100, f"{len(r.text)} bytes (SPA预期小HTML)")

# 3. Vite代理 -> API健康检查
r = httpx.get(f"{BASE}/api/health", timeout=10)
chk("API代理 Health 200", r.status_code == 200)

# 4. Vite代理 -> 正常仿真
GCODE = "G21 G17 G90\nG00 Z50.\nG00 X0. Y0.\nG01 Z5. F500\nG01 X30. Y10. F800\nG01 X50. Y25. F800\nG00 Z50."

r = httpx.post(f"{BASE}/api/simulation/run", json={
    "project_id": "vite_proxy_test",
    "voxel_size": 2.0, "tool_diameter": 8.0, "tool_length": 40.0,
    "tool_type": "flat", "gcode": GCODE,
    "safe_z_height": 10.0, "stock_stl_path": "",
}, timeout=120)

data = r.json()
d = data.get("data", {})
chk("Vite代理仿真 HTTP 200", r.status_code == 200)
chk("Vite代理仿真 code=0", data.get("code") == 0)
chk("Vite代理 collision_detected存在", "collision_detected" in d)
chk("Vite代理 workpiece_stl_path存在",
    "workpiece_stl_path" in d.get("simulation_result", {}))
print(f"  [INFO] task_id={d.get('task_id')}, collision={d.get('collision_detected')}")
print(f"  [INFO] stl_path={d.get('simulation_result',{}).get('workpiece_stl_path')}")

# 5. Vite代理 -> 碰撞仿真
GCODE_COL = "G21 G17 G90\nG00 Z80.\nG00 X0. Y0.\nG01 Z-15. F500\nG01 X20. F800\nG01 X40.\nG00 Z80."

r2 = httpx.post(f"{BASE}/api/simulation/run", json={
    "project_id": "vite_collision",
    "voxel_size": 2.0, "tool_diameter": 8.0, "tool_length": 40.0,
    "tool_type": "flat", "gcode": GCODE_COL,
    "safe_z_height": 10.0, "stock_stl_path": "",
}, timeout=60)

d2 = r2.json().get("data", {})
cd2 = d2.get("collision_details", {})
chk("Vite碰撞 collision_detected=true", d2.get("collision_detected") == True,
    f"got {d2.get('collision_detected')}")
chk("Vite碰撞 count>0", cd2.get("count", 0) > 0)
chk("Vite碰撞 severity非空", cd2.get("severity") != "none")
print(f"  [INFO] severity={cd2.get('severity')}, count={cd2.get('count')}")

# 6. 连续3次快速调用
print()
print("  [INFO] 连续3次代理调用...")
all_ok = True
for i in range(3):
    r = httpx.post(f"{BASE}/api/simulation/run", json={
        "project_id": f"vite_rapid_{i}",
        "voxel_size": 2.0, "tool_diameter": 8.0, "tool_length": 40.0,
        "tool_type": "flat", "gcode": GCODE,
        "safe_z_height": 10.0, "stock_stl_path": "",
    }, timeout=60)
    ok = r.status_code == 200 and r.json().get("code") == 0
    if not ok: all_ok = False
    print(f"    #{i}: {'OK' if ok else 'FAIL'} ({r.status_code})")
chk("3次快速调用全部成功", all_ok)

# Summary
print()
total = passed + failed
print(f"FRONTEND PROXY TEST: {passed} passed, {failed} failed, {total} total")
sys.exit(0 if failed == 0 else 1)
