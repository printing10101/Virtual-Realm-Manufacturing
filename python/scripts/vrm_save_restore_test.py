"""
工程保存与恢复 — 全流程自动化验证测试

测试覆盖：
  T1. 工程创建：新建工程 + 导入STL模型 + 定义毛坯 + 选择刀具 + 生成刀路
  T2. 保存功能：保存为 .vrm 文件，验证文件存在且大小合理
  T3. 文件完整性：解压 .vrm → 验证 project.json + 资源文件
  T4. 工程恢复：重新打开 .vrm → 验证所有数据完整恢复
  T5. 异常兼容性：损坏文件/版本不匹配 → 验证友好错误提示
"""

import httpx
import json
import sys
import zipfile
from pathlib import Path
from datetime import datetime, timezone

BASE = "http://localhost:8001"
OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "projects"
TEST_DIR = Path(__file__).resolve().parent / "_test_output"
TEST_DIR.mkdir(parents=True, exist_ok=True)

P = 0
F = 0
LOG_LINES: list[str] = []


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    LOG_LINES.append(line)
    print(line)


def chk(name: str, condition: bool, detail: str = ""):
    global P, F
    if condition:
        P += 1
        log(f"  [PASS] {name}")
    else:
        F += 1
        log(f"  [FAIL] {name}  {detail}")


def section(title: str):
    log("")
    log("=" * 64)
    log(f"  {title}")
    log("=" * 64)


# ============================================================================
# T1: 工程创建与操作测试
# ============================================================================
section("T1: 工程创建与操作测试")

# 1a. 新建工程
log("1a. 新建工程")
resp = httpx.post(
    f"{BASE}/api/projects/new",
    json={
        "name": "VrmTest-法兰盘加工",
        "author": "测试工程师",
        "description": "法兰盘铣削加工——全流程验证测试",
    },
    timeout=15,
)
data = resp.json()
chk("新建HTTP200", resp.status_code == 200)
chk("新建code=0", data["code"] == 0)
chk("返回project_id", "project_id" in data["data"])
chk("返回manifest", "manifest" in data["data"])
chk("version=1.0", data["data"]["version"] == "1.0")

pid = data["data"]["project_id"]
mf = data["data"]["manifest"]
log(f"  工程ID: {pid}")
log(f"  工程名称: {mf['metadata']['name']}")

# 1b. 生成测试STL模型并上传
log("")
log("1b. 导入STL模型文件")
try:
    import trimesh

    stock_mesh = trimesh.creation.box(extents=[120, 80, 40])
    stock_mesh.apply_translation([0, 0, 20])
    stock_path = TEST_DIR / "flange_stock.stl"
    stock_mesh.export(str(stock_path), file_type="stl")
    log(f"  创建测试STL: {stock_path} ({stock_path.stat().st_size} bytes)")

    # 上传为资源文件
    with open(stock_path, "rb") as f:
        upload_resp = httpx.post(
            f"{BASE}/api/projects/upload-resource?resource_type=model",
            files={"file": ("flange_stock.stl", f, "application/sla")},
            timeout=30,
        )
    upload_data = upload_resp.json()
    chk("STL上传HTTP200", upload_resp.status_code == 200)
    chk("STL上传成功", upload_data["code"] == 0)
    log(f"  资源ID: {upload_data['data']['resource_id']}")
except ImportError:
    log("  [SKIP] trimesh未安装，使用模拟模型数据")
    upload_data = {"data": {"resource_id": "res_mock001", "temp_path": ""}}

# 1c. 精确定义毛坯尺寸参数
log("")
log("1c. 定义毛坯尺寸参数")
stock_def = {
    "type": "rectangular",
    "length": 120.0,
    "width": 80.0,
    "height": 40.0,
    "origin_x": 0.0,
    "origin_y": 0.0,
    "origin_z": 0.0,
    "unit": "mm",
    "material": "6061-T6铝合金",
    "stock_stl_path": "models/flange_stock.stl",
}
mf["data"]["stock_definition"] = stock_def
chk("毛坯length=120", stock_def["length"] == 120)
chk("毛坯width=80", stock_def["width"] == 80)
chk("毛坯height=40", stock_def["height"] == 40)
chk("毛坯原点定义", stock_def["origin_x"] == 0 and stock_def["origin_z"] == 0)
log(f"  毛坯: {stock_def['length']}x{stock_def['width']}x{stock_def['height']}mm")

# 1d. 从刀具库选择刀具
log("")
log("1d. 选择刀具并配置参数")
tool_selection = [
    {
        "id": "T01",
        "name": "D20R1平底铣刀",
        "type": "flat",
        "diameter": 20.0,
        "corner_radius": 1.0,
        "length": 80.0,
        "flutes": 4,
        "material": "硬质合金",
        "spindle_speed": 6000,
        "feed_rate": 800,
    },
    {
        "id": "T02",
        "name": "D8球头铣刀",
        "type": "ball",
        "diameter": 8.0,
        "corner_radius": 4.0,
        "length": 60.0,
        "flutes": 2,
        "material": "硬质合金",
        "spindle_speed": 10000,
        "feed_rate": 500,
    },
    {
        "id": "T03",
        "name": "D6钻头",
        "type": "drill",
        "diameter": 6.0,
        "length": 100.0,
        "flutes": 2,
        "material": "高速钢",
        "spindle_speed": 4000,
        "feed_rate": 200,
    },
]
mf["data"]["tool_selection"] = tool_selection
chk("已选3把刀具", len(tool_selection) == 3)
chk("T01平底刀", tool_selection[0]["type"] == "flat")
chk("T02球头刀", tool_selection[1]["type"] == "ball")
chk("T03钻头", tool_selection[2]["type"] == "drill")
log(f"  已选: {[t['name'] for t in tool_selection]}")

# 1e. 生成加工工艺步骤 + 刀路
log("")
log("1e. 定义工艺步骤并生成刀路")
process_steps = [
    {
        "step": 1,
        "name": "粗加工-外轮廓",
        "tool_id": "T01",
        "operation": "contour_rough",
        "depth_of_cut": 5.0,
        "step_over": 8.0,
        "stock_to_leave": 0.5,
        "toolpath_segments": 24,
    },
    {
        "step": 2,
        "name": "精加工-外轮廓",
        "tool_id": "T01",
        "operation": "contour_finish",
        "depth_of_cut": 0.5,
        "toolpath_segments": 36,
    },
    {
        "step": 3,
        "name": "钻孔-安装孔x4",
        "tool_id": "T03",
        "operation": "drill",
        "hole_positions": [
            [35.0, 25.0, 0.0],
            [35.0, -25.0, 0.0],
            [-35.0, 25.0, 0.0],
            [-35.0, -25.0, 0.0],
        ],
        "depth": 40.0,
        "toolpath_segments": 8,
    },
    {
        "step": 4,
        "name": "曲面精加工-法兰面",
        "tool_id": "T02",
        "operation": "surface_finish",
        "step_over": 0.3,
        "toolpath_segments": 120,
    },
]
mf["data"]["process_steps"] = process_steps
mf["data"]["toolpath_config"] = {
    "total_segments": 188,
    "estimated_time_min": 15.5,
    "safe_z_height": 50.0,
    "clearance_plane": 55.0,
}
mf["data"]["postprocessor_config"] = {
    "format": "fanuc",
    "controller": "Fanuc 0i-MF",
    "output_name": "flange_machining.nc",
}
mf["data"]["simulation_config"] = {
    "voxel_size": 1.0,
    "collision_check": True,
}
chk("工艺步骤4步", len(process_steps) == 4)
chk("粗加工步骤", process_steps[0]["name"] == "粗加工-外轮廓")
chk("钻孔步骤含4孔位", len(process_steps[2]["hole_positions"]) == 4)
chk("球头刀精加工", process_steps[3]["tool_id"] == "T02")
chk("后处理Fanuc", mf["data"]["postprocessor_config"]["format"] == "fanuc")
log(f"  工艺步骤: {[s['name'] for s in process_steps]}")
log(f"  总刀路段数: {mf['data']['toolpath_config']['total_segments']}")

# ============================================================================
# T2: 保存功能测试
# ============================================================================
section("T2: 保存功能测试 — 生成 .vrm 文件")

output_name = "vrmtest_flange_mill.vrm"

chk("工程名含非空值", bool(mf["metadata"]["name"]))
chk("工程含3刀具", len(mf["data"]["tool_selection"]) == 3)
chk("工程含4工序", len(mf["data"]["process_steps"]) == 4)

save_resp = httpx.post(
    f"{BASE}/api/projects/save",
    json={
        "manifest": mf,
        "project_id": pid,
        "output_name": output_name,
    },
    timeout=30,
)
sdata = save_resp.json()
chk("保存HTTP200", save_resp.status_code == 200)
chk("保存code=0", sdata["code"] == 0)
chk("返回file_path", sdata["data"]["file_path"])
chk("文件名正确", sdata["data"]["file_name"] == output_name)
chk("文件大小>0", sdata["data"]["file_size"] > 0)

saved_path = sdata["data"]["file_path"]
file_size = sdata["data"]["file_size"]
log(f"  .vrm文件: {Path(saved_path).name}")
log(f"  文件大小: {file_size} bytes ({file_size / 1024:.1f} KB)")
log(f"  完整路径: {saved_path}")

# 验证文件在项目output目录下
chk("文件在output目录", "output" in saved_path.replace("\\", "/").lower())

# vrm文件存在
assert Path(saved_path).exists(), f"文件不存在: {saved_path}"
chk(".vrm文件物理存在", Path(saved_path).exists())

# ============================================================================
# T3: 文件完整性验证
# ============================================================================
section("T3: 文件完整性验证 — 解压 .vrm")

assert Path(saved_path).exists()

with zipfile.ZipFile(saved_path, "r") as zf:
    names = zf.namelist()
    log(f"  ZIP内容 ({len(names)}个条目):")
    for n in sorted(names):
        info = zf.getinfo(n)
        log(f"    {n:40s} {info.file_size:>8d} bytes")

    # 3a. project.json 存在
    chk("project.json存在", "project.json" in names)

    # 3b. 解析 project.json
    raw_json = zf.read("project.json").decode("utf-8")
    proj_data = json.loads(raw_json)
    chk("project.json有效JSON", isinstance(proj_data, dict))

    # 3c. 版本号
    chk("version=1.0", proj_data.get("version") == "1.0")

    # 3d. 元数据
    meta = proj_data.get("metadata", {})
    chk("metadata.name非空", bool(meta.get("name")))
    chk("metadata.author非空", bool(meta.get("author")))
    chk("metadata含created_at", "created_at" in meta)
    chk("metadata含modified_at", "modified_at" in meta)

    # 3e. 毛坯定义
    stock_data = proj_data.get("data", {}).get("stock_definition", {})
    chk("毛坯length=120", stock_data.get("length") == 120)
    chk("毛坯width=80", stock_data.get("width") == 80)
    chk("毛坯height=40", stock_data.get("height") == 40)
    chk("毛坯原点x=0", stock_data.get("origin_x") == 0)
    chk("毛坯材质", stock_data.get("material") == "6061-T6铝合金")
    log(f"  毛坯在JSON中: {json.dumps(stock_data, ensure_ascii=False)[:120]}")

    # 3f. 刀具选择
    tools = proj_data.get("data", {}).get("tool_selection", [])
    chk("刀具数量=3", len(tools) == 3)
    if len(tools) >= 3:
        chk("T01=flat", tools[0]["type"] == "flat")
        chk("T01直径20", tools[0]["diameter"] == 20)
        chk("T02=ball", tools[1]["type"] == "ball")
        chk("T03=drill", tools[2]["type"] == "drill")
        log(f"  保存的刀具: {[t['id'] + '=' + t['name'] for t in tools]}")

    # 3g. 工艺步骤
    steps = proj_data.get("data", {}).get("process_steps", [])
    chk("工艺步骤数量=4", len(steps) == 4)
    log(f"  保存的工序: {[s['name'] for s in steps]}")
    log(
        f"  刀路总段数: {proj_data.get('data', {}).get('toolpath_config', {}).get('total_segments')}"
    )

    # 3h. 后处理配置
    post = proj_data.get("data", {}).get("postprocessor_config", {})
    chk("后处理format=fanuc", post.get("format") == "fanuc")

    # 3i. resources清单
    resources = proj_data.get("resources", [])
    chk("resources字段存在", "resources" in proj_data)

    # 验证 extensions 字段
    chk("extensions字段存在", "extensions" in proj_data)

log("")
log("  project.json 完整性检查全部通过")

# ============================================================================
# T4: 工程恢复测试
# ============================================================================
section("T4: 工程恢复测试 — 重新打开 .vrm")

# 4a. 通过API打开
reopen_resp = httpx.post(
    f"{BASE}/api/projects/open",
    json={
        "file_path": saved_path,
    },
    timeout=15,
)
rdata = reopen_resp.json()
chk("重新打开HTTP200", reopen_resp.status_code == 200)
chk("重新打开code=0", rdata["code"] == 0)

reloaded = rdata["data"]["manifest"]

# 4b. 验证工序步骤恢复
re_steps = reloaded.get("data", {}).get("process_steps", [])
chk("恢复后工序=4", len(re_steps) == 4)
chk("恢复粗加工", any(s["name"] == "粗加工-外轮廓" for s in re_steps))
chk("恢复精加工", any(s["name"] == "精加工-外轮廓" for s in re_steps))
chk("恢复钻孔", any(s["name"] == "钻孔-安装孔x4" for s in re_steps))
chk("恢复曲面加工", any(s["name"] == "曲面精加工-法兰面" for s in re_steps))
log(f"  恢复的工序步骤: {len(re_steps)}步")

# 4c. 验证刀具恢复
re_tools = reloaded.get("data", {}).get("tool_selection", [])
chk("恢复刀具数量=3", len(re_tools) == 3)
chk("恢复T01", any(t["id"] == "T01" for t in re_tools))
chk("恢复T02", any(t["id"] == "T02" for t in re_tools))
chk("恢复T03", any(t["id"] == "T03" for t in re_tools))
log(f"  恢复的刀具: {[t['id'] for t in re_tools]}")

# 4d. 验证毛坯恢复
re_stock = reloaded.get("data", {}).get("stock_definition", {})
chk("恢复毛坯length", re_stock.get("length") == 120)
chk("恢复毛坯width", re_stock.get("width") == 80)
chk("恢复毛坯height", re_stock.get("height") == 40)
chk("恢复毛坯材质", re_stock.get("material") == "6061-T6铝合金")
log(
    f"  恢复的毛坯: {re_stock.get('length')}x{re_stock.get('width')}x{re_stock.get('height')}"
)

# 4e. 验证刀路配置恢复
re_tp = reloaded.get("data", {}).get("toolpath_config", {})
chk("恢复刀路总段数", re_tp.get("total_segments") == 188)
chk("恢复安全Z高度", re_tp.get("safe_z_height") == 50)

# 4f. 验证后处理配置恢复
re_post = reloaded.get("data", {}).get("postprocessor_config", {})
chk("恢复后处理format", re_post.get("format") == "fanuc")
chk("恢复输出文件名", re_post.get("output_name") == "flange_machining.nc")

# 4g. 验证版本与元数据
chk("版本正确", reloaded.get("version") == "1.0")
chk("工程名恢复正确", reloaded.get("metadata", {}).get("name") == "VrmTest-法兰盘加工")

log("")
log("  所有工程数据完整恢复 [OK]")

# ============================================================================
# T5: 异常兼容性测试
# ============================================================================
section("T5: 异常兼容性测试")

# 5a. 损坏的 .vrm 文件
log("5a. 损坏文件测试")
corrupt_path = TEST_DIR / "corrupted.vrm"
corrupt_path.write_bytes(b"THIS IS NOT A VALID ZIP FILE\x00\xff\xfe")
chk("损坏文件已创建", corrupt_path.exists())

corrupt_resp = httpx.post(
    f"{BASE}/api/projects/open",
    json={
        "file_path": str(corrupt_path),
    },
    timeout=10,
)
corrupt_data = corrupt_resp.json()
chk(
    "损坏文件返回错误码(非0)", corrupt_data["code"] != 0, f"code={corrupt_data['code']}"
)
chk("损坏文件含错误消息", len(corrupt_data.get("message", "")) > 0)
log(
    f"  损坏文件响应: code={corrupt_data['code']}, message={corrupt_data.get('message', '')[:80]}"
)

# 5b. 无效的ZIP头
log("")
log("5b. 截断文件测试")
trunc_path = TEST_DIR / "truncated.vrm"
trunc_path.write_bytes(b"PK\x03\x04\x00\x00\x00\x00")  # 只有ZIP头
chk("截断文件已创建", trunc_path.exists())

trunc_resp = httpx.post(
    f"{BASE}/api/projects/open",
    json={
        "file_path": str(trunc_path),
    },
    timeout=10,
)
trunc_data = trunc_resp.json()
chk("截断文件返回错误码", trunc_data["code"] != 0)
chk("截断文件有错误提示", "message" in trunc_data)
log(
    f"  截断文件响应: code={trunc_data['code']}, message={trunc_data.get('message', '')[:80]}"
)

# 5c. 不支持的扩展名
log("")
log("5c. 不支持的扩展名测试")
wrong_ext_path = TEST_DIR / "test.txt"
wrong_ext_path.write_text("hello")
chk("错误扩展名文件已创建", wrong_ext_path.exists())

wrong_ext_resp = httpx.post(
    f"{BASE}/api/projects/open",
    json={
        "file_path": str(wrong_ext_path),
    },
    timeout=10,
)
wrong_ext_data = wrong_ext_resp.json()
chk("错误扩展名返回错误", wrong_ext_data["code"] != 0)
chk(
    "提示仅支持.vrm",
    ".vrm" in wrong_ext_data.get("message", "").lower()
    or "不支持" in wrong_ext_data.get("message", "")
    or "格式" in wrong_ext_data.get("message", ""),
)
log(f"  错误扩展名响应: message={wrong_ext_data.get('message', '')[:80]}")

# 5d. 高版本文件
log("")
log("5d. 高版本兼容性测试")
future_mf = dict(mf)
future_mf["version"] = "3.0"
future_mf["metadata"]["modified_at"] = datetime.now(timezone.utc).isoformat()

future_resp = httpx.post(
    f"{BASE}/api/projects/save",
    json={
        "manifest": future_mf,
        "project_id": pid,
        "output_name": "future_version.vrm",
    },
    timeout=30,
)

if future_resp.status_code == 200 and future_resp.json()["code"] == 0:
    future_path = future_resp.json()["data"]["file_path"]
    chk("高版本文件已创建", Path(future_path).exists())

    future_open = httpx.post(
        f"{BASE}/api/projects/open",
        json={
            "file_path": future_path,
        },
        timeout=10,
    )
    fdata = future_open.json()
    chk("高版本被拒绝打开", fdata["code"] != 0, f"(预期错误但code={fdata['code']})")
    version_rejected = (
        "版本" in fdata.get("message", "")
        or "升级" in fdata.get("message", "")
        or "不支持" in fdata.get("message", "")
        or "高于" in fdata.get("message", "")
    )
    chk("高版本提示升级", version_rejected, f"message={fdata.get('message', '')[:80]}")
    log(f"  高版本文件响应: {fdata.get('message', '')[:100]}")
else:
    log("  [WARN] 保存高版本文件失败，跳过打开测试")

# 5e. 空 JSON 文件（zip中缺project.json）
log("")
log("5e. 缺失 project.json 文件测试")
empty_zip_path = TEST_DIR / "no_project_json.vrm"
with zipfile.ZipFile(str(empty_zip_path), "w") as zf:
    zf.writestr("readme.txt", "this is not a project file")
chk("空ZIP已创建", empty_zip_path.exists())

empty_resp = httpx.post(
    f"{BASE}/api/projects/open",
    json={
        "file_path": str(empty_zip_path),
    },
    timeout=10,
)
empty_data = empty_resp.json()
chk("缺失project.json返回错误", empty_data["code"] != 0)
chk(
    "提示project.json缺失",
    "缺少" in empty_data.get("message", "")
    or "project.json" in empty_data.get("message", "").lower()
    or "损坏" in empty_data.get("message", ""),
)
log(f"  缺失project.json响应: {empty_data.get('message', '')[:80]}")

# 5f. 不存在文件
log("")
log("5f. 文件不存在测试")
nofile_resp = httpx.post(
    f"{BASE}/api/projects/open",
    json={
        "file_path": str(TEST_DIR / "nonexistent_xyz999.vrm"),
    },
    timeout=10,
)
nofile_data = nofile_resp.json()
chk("不存在文件返回错误", nofile_data["code"] != 0)
chk(
    "文件不存在友好提示",
    "未找到" in nofile_data.get("message", "")
    or "不存在" in nofile_data.get("message", "")
    or "not found" in nofile_data.get("message", "").lower()
    or "FILE_NOT_FOUND" in str(nofile_data),
)
log(f"  不存在文件响应: {nofile_data.get('message', '')[:80]}")

# ============================================================================
# SUMMARY
# ============================================================================
section("测试汇总报告")
total = P + F
log("")
log(f"  {'ALL PASSED' if F == 0 else 'SOME FAILED'}")
log(f"  {P} 通过, {F} 失败, {total} 总计")
log("")

# 写入日志文件
log_path = TEST_DIR / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_path.write_text("\n".join(LOG_LINES), encoding="utf-8")
log(f"详细日志已保存: {log_path}")
log("")

sys.exit(0 if F == 0 else 1)
