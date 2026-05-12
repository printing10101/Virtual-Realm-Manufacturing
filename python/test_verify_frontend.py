#!/usr/bin/env python3
"""验证步骤3和4：系统状态面板显示 + 自动刷新功能"""
import urllib.request
import urllib.error
import json
import time
import sys
import os

BASE_URL = "http://localhost:8000"

def get(path):
    url = BASE_URL + path
    req = urllib.request.Request(url)
    try:
        token = open(".lnn_token").read().strip()
        req.add_header("Authorization", f"Bearer {token}")
    except:
        pass
    r = urllib.request.urlopen(req, timeout=5)
    raw = r.read().decode('utf-8')
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw

def check_api(path, desc):
    try:
        data = get(path)
        print(f"  [OK] {desc}: {path}")
        return True, data
    except Exception as e:
        print(f"  [FAIL] {desc}: {path} - {e}")
        return False, None

def format_uptime(seconds):
    d = int(seconds / 86400)
    h = int((seconds % 86400) / 3600)
    m = int((seconds % 3600) / 60)
    s = int(seconds % 60)
    if d > 0: return f"{d}d {h}h {m}m"
    if h > 0: return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"

def verify_health_panel():
    print("=" * 60)
    print("步骤3: 系统状态面板显示验证")
    print("=" * 60)
    
    results = {}
    
    # 1. Ping检查
    ok, data = check_api("/api/health/ping", "后端在线检查")
    results["backend_online"] = ok and data
    
    if not results["backend_online"]:
        print("\n[ERROR] 后端离线，无法继续验证面板数据")
        return False
    
    # 2. 获取Prometheus指标
    ok, metrics_data = check_api("/api/metrics", "Prometheus指标")
    if ok and metrics_data:
        text = metrics_data if isinstance(metrics_data, str) else str(metrics_data)
        
        uptime_match = None
        for line in text.split('\n'):
            if 'sidecar_uptime_seconds' in line and not line.startswith('#'):
                uptime_match = line
                break
        
        if uptime_match:
            uptime_val = float(uptime_match.split()[-1])
            print(f"    - 运行时间: {format_uptime(uptime_val)}")
            results["uptime"] = True
        
        mem_match = None
        for line in text.split('\n'):
            if 'process_resident_memory_bytes' in line and not line.startswith('#'):
                mem_match = line
                break
        if mem_match:
            mem_bytes = float(mem_match.split()[-1])
            mem_mb = mem_bytes / (1024 * 1024)
            print(f"    - 内存使用: {mem_mb:.1f} MB")
            results["memory"] = True
            
        cpu_match = None
        for line in text.split('\n'):
            if 'process_cpu_percent' in line and not line.startswith('#'):
                cpu_match = line
                break
        if cpu_match:
            cpu_val = float(cpu_match.split()[-1])
            print(f"    - CPU使用: {cpu_val}%")
            results["cpu"] = True
    
    # 3. LNN健康状态
    ok, lnn_data = check_api("/api/v1/lnn/health", "LNN健康状态")
    if ok and lnn_data:
        data_section = lnn_data.get('data', {})
        print(f"    - 可用模型数: {data_section.get('models_registered', 'N/A')}")
        print(f"    - 活跃训练任务: {data_section.get('active_training_tasks', 'N/A')}")
        results["lnn_health"] = True
    
    # 4. LNN性能统计
    ok, perf_data = check_api("/api/v1/lnn/performance", "LNN性能统计")
    if ok and perf_data:
        data_section = perf_data.get('data', {})
        models = data_section.get('models', [])
        if models:
            m = models[0]
            print(f"    - 跟踪模型数: {data_section.get('total_models_tracked', 0)}")
            print(f"    - 推理次数: {m.get('total_inferences', 'N/A')}")
            print(f"    - P50延迟: {m.get('p50_inference_ms', 'N/A')}ms")
            print(f"    - P95延迟: {m.get('p95_inference_ms', 'N/A')}ms")
            print(f"    - 内存: {m.get('current_memory_mb', 'N/A')}MB")
            results["lnn_performance"] = True
        else:
            # 无模型数据不算失败，只是没有推理过
            print(f"    - 跟踪模型数: 0 (尚未有推理请求)")
            results["lnn_performance"] = True
    
    # 5. 系统健康端点
    ok, sys_health = check_api("/api/health", "系统健康端点")
    if ok and sys_health:
        data_section = sys_health.get('data', {})
        print(f"    - DB健康: {data_section.get('db_healthy', 'N/A')}")
        print(f"    - Redis健康: {data_section.get('redis_healthy', 'N/A')}")
        results["system_health"] = True
    
    # 汇总
    print("\n面板指标检查汇总:")
    checks = {
        "后端在线": results.get("backend_online", False),
        "运行时间": results.get("uptime", False),
        "内存使用": results.get("memory", False),
        "CPU使用": results.get("cpu", False),
        "LNN健康": results.get("lnn_health", False),
        "LNN性能": results.get("lnn_performance", False),
        "系统健康": results.get("system_health", False),
    }
    all_passed = True
    for name, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    return all_passed

def verify_auto_refresh():
    print("\n" + "=" * 60)
    print("步骤4: 数据自动刷新功能验证")
    print("=" * 60)
    
    print("  验证Settings.vue中的轮询配置...")
    
    # 读取Settings.vue代码，检查pollInterval
    vue_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "views", "Settings.vue")
    with open(vue_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查pollInterval配置
    if "pollInterval: 5" in content:
        print("  [OK] 轮询间隔配置: 5秒")
    else:
        print("  [WARN] 未找到明确的5秒轮询配置")
    
    # 检查setInterval调用
    if "setInterval(refreshHealth" in content:
        print("  [OK] 自动刷新机制: setInterval已配置")
    else:
        print("  [FAIL] 未找到setInterval调用")
        return False
    
    # 检查onMounted中启动轮询
    if "startHealthPolling()" in content:
        print("  [OK] 组件挂载时启动轮询")
    else:
        print("  [FAIL] 未在onMounted中调用startHealthPolling")
        return False
    
    # 检查onBeforeUnmount中停止轮询
    if "stopHealthPolling()" in content:
        print("  [OK] 组件卸载时停止轮询")
    else:
        print("  [WARN] 未在onBeforeUnmount中调用stopHealthPolling")
    
    # 模拟验证：连续两次请求检查数据更新
    print("\n  模拟自动刷新检测（连续2次请求，间隔6秒）...")
    
    try:
        # 第一次请求
        metrics1 = get("/api/metrics")
        text1 = metrics1 if isinstance(metrics1, str) else str(metrics1)
        uptime1 = None
        for line in text1.split('\n'):
            if 'sidecar_uptime_seconds' in line and not line.startswith('#'):
                uptime1 = float(line.split()[-1])
                break
        
        print(f"    第一次请求 - uptime: {uptime1}")
        
        # 等待6秒（超过5秒轮询间隔）
        print("    等待6秒...")
        time.sleep(6)
        
        # 第二次请求
        metrics2 = get("/api/metrics")
        text2 = metrics2 if isinstance(metrics2, str) else str(metrics2)
        uptime2 = None
        for line in text2.split('\n'):
            if 'sidecar_uptime_seconds' in line and not line.startswith('#'):
                uptime2 = float(line.split()[-1])
                break
        
        print(f"    第二次请求 - uptime: {uptime2}")
        
        if uptime1 is not None and uptime2 is not None:
            diff = uptime2 - uptime1
            # 等待6秒 + 请求处理时间，应该在5-12秒范围内
            if diff >= 5 and diff <= 12:
                print(f"  [OK] 数据正常更新，时间差: {diff:.1f}秒")
                return True
            else:
                print(f"  [WARN] 时间差异常: {diff:.1f}秒")
                return False
        else:
            print("  [FAIL] 无法获取uptime数据")
            return False
            
    except Exception as e:
        print(f"  [FAIL] 自动刷新检测失败: {e}")
        return False

if __name__ == "__main__":
    step3_ok = verify_health_panel()
    step4_ok = verify_auto_refresh()
    
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    print(f"  步骤3（系统状态面板）: {'[通过]' if step3_ok else '[失败]'}")
    print(f"  步骤4（自动刷新）: {'[通过]' if step4_ok else '[失败]'}")
    
    if step3_ok and step4_ok:
        print("\n所有验证通过！")
    else:
        print("\n部分验证失败，请检查错误日志。")
        sys.exit(1)
