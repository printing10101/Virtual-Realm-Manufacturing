"""工程管理 API 集成测试。"""

import httpx
import sys

BASE = "http://localhost:8001"
P = 0
F = 0


def chk(n, c, d=""):
    global P, F
    if c:
        P += 1
        print(f"  [PASS] {n}")
    else:
        F += 1
        print(f"  [FAIL] {n}  {d}")


# 1. 健康检查
print("1. 健康检查")
r = httpx.get(f"{BASE}/api/health", timeout=5)
chk("Health 200", r.status_code == 200)

# 2. 新建工程
print("\n2. 新建工程")
resp = httpx.post(
    f"{BASE}/api/projects/new",
    json={"name": "集成测试-铣削", "author": "测试脚本", "description": "API集成测试"},
    timeout=10,
)
data = resp.json()
chk("新建 HTTP 200", resp.status_code == 200)
chk("新建 code=0", data["code"] == 0)
chk("新建 返回project_id", "project_id" in data["data"])
chk("新建 返回manifest", "manifest" in data["data"])
chk("新建 version=1.0", data["data"]["version"] == "1.0")
pid = data["data"]["project_id"]
mf = data["data"]["manifest"]
print(f"  工程ID: {pid}, 名称: {mf['metadata']['name']}")

# 3. 保存工程
print("\n3. 保存工程")
save_resp = httpx.post(
    f"{BASE}/api/projects/save",
    json={
        "manifest": mf,
        "project_id": pid,
        "output_name": "integration_test.vrm",
    },
    timeout=10,
)
sdata = save_resp.json()
chk("保存 HTTP 200", save_resp.status_code == 200)
chk("保存 code=0", sdata["code"] == 0)
chk("保存 返回file_path", sdata["data"]["file_path"])
chk("保存 文件名正确", sdata["data"]["file_name"] == "integration_test.vrm")
saved_path = sdata["data"]["file_path"]
print(f"  保存路径: {saved_path}")

# 4. 打开工程
print("\n4. 打开工程")
open_resp = httpx.post(
    f"{BASE}/api/projects/open",
    json={
        "file_path": saved_path,
    },
    timeout=10,
)
odata = open_resp.json()
chk("打开 HTTP 200", open_resp.status_code == 200)
chk("打开 code=0", odata["code"] == 0)
chk("打开 返回manifest", "manifest" in odata["data"])
chk("打开 名称一致", odata["data"]["manifest"]["metadata"]["name"] == "集成测试-铣削")

# 5. 另存为
print("\n5. 另存为")
sa_resp = httpx.post(
    f"{BASE}/api/projects/save-as",
    json={
        "manifest": mf,
        "project_id": pid,
        "output_name": "integration_copy.vrm",
    },
    timeout=10,
)
sadata = sa_resp.json()
chk("另存为 HTTP 200", sa_resp.status_code == 200)
chk("另存为 code=0", sadata["code"] == 0)
chk("另存为 文件名", sadata["data"]["file_name"] == "integration_copy.vrm")

# 6. 列表
print("\n6. 工程列表")
list_resp = httpx.get(f"{BASE}/api/projects/list", timeout=10)
ldata = list_resp.json()
chk("列表 HTTP 200", list_resp.status_code == 200)
chk("列表 code=0", ldata["code"] == 0)
items = ldata["data"]["items"]
chk("列表 含工程", len(items) >= 2)

# 7. 工程列表含正确字段
print("\n7. 列表数据验证")
sample = items[0]
chk("含name", "name" in sample)
chk("含path", "path" in sample)
chk("含file_size", "file_size" in sample and sample["file_size"] > 0)

# 8. 删除工程
print("\n8. 删除工程")
del_resp = httpx.delete(f"{BASE}/api/projects/integration_copy.vrm", timeout=10)
chk("删除 HTTP 200", del_resp.status_code == 200)
chk("删除 code=0", del_resp.json()["code"] == 0)

# 9. 扩展字段
print("\n9. extensions字段")
mf["extensions"] = {
    "simulation_result": {"task_id": "sim_001"},
    "custom_plugin": {"enabled": True},
}
ext_resp = httpx.post(
    f"{BASE}/api/projects/save",
    json={
        "manifest": mf,
        "project_id": pid,
        "output_name": "integration_ext_test.vrm",
    },
    timeout=10,
)
# 验证 extensions 可保存并重新读取
open_ext_resp = httpx.post(
    f"{BASE}/api/projects/open",
    json={
        "file_path": ext_resp.json()["data"]["file_path"],
    },
    timeout=10,
)
ext_manifest = open_ext_resp.json()["data"]["manifest"]
chk(
    "extensions保存-读取",
    ext_manifest["extensions"]["simulation_result"]["task_id"] == "sim_001",
)
chk("extensions多层次", ext_manifest["extensions"]["custom_plugin"]["enabled"])

# 10. 版本检查
print("\n10. 版本兼容性")
chk("版本号1.0", data["data"]["version"] == "1.0")

# Summary
total = P + F
print(f"\n{'=' * 60}")
print(f"PROJECT API TEST: {P} passed, {F} failed, {total} total")
print(f"{'=' * 60}")
sys.exit(0 if F == 0 else 1)
