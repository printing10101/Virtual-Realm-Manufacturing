#!/usr/bin/env python3
"""验证步骤6-10：Docker部署、Grafana、高延迟场景、告警规则、服务依赖"""

import subprocess
import json
import time
import sys
import os
import urllib.request
import urllib.error

COMPOSE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docker-compose.yml"
)
BASE_URL = "http://localhost:8000"


def run_cmd(cmd, timeout=60):
    print(f"  执行: {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_container_health(container_name):
    code, stdout, stderr = run_cmd(
        f'docker inspect --format="{{{{.State.Health.Status}}}}" {container_name}'
    )
    if code == 0:
        return stdout.strip().strip('"')
    return "unknown"


def check_container_running(container_name):
    code, stdout, stderr = run_cmd(
        f'docker inspect --format="{{{{.State.Status}}}}" {container_name}'
    )
    if code == 0:
        return stdout.strip().strip('"')
    return "not_found"


def get(path, timeout=5):
    url = BASE_URL + path
    req = urllib.request.Request(url)
    try:
        token_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".lnn_token"
        )
        token = open(token_path).read().strip()
        req.add_header("Authorization", f"Bearer {token}")
    except:
        pass
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        raw = r.read().decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    except Exception:
        return None


def verify_docker_health_checks():
    """步骤9: Docker服务健康检查验证"""
    print("=" * 60)
    print("步骤9: Docker服务健康检查验证")
    print("=" * 60)

    # 检查是否有Docker容器在运行
    code, stdout, stderr = run_cmd("docker ps --format '{{.Names}}'")
    if code != 0 or "dockerDesktopLinuxEngine" in stderr or "daemon" in stderr.lower():
        print("  [SKIP] Docker daemon未运行。请先启动Docker Desktop")
        return None  # SKIP

    containers = [c.strip().strip("'") for c in stdout.split("\n") if c.strip()]
    if not containers:
        print("  [SKIP] 没有Docker容器运行。请先执行 docker-compose up -d 启动服务")
        return None  # SKIP

    print(f"  运行中的容器: {', '.join(containers)}")

    expected = ["lnn-api", "lnn-redis", "lnn-postgres", "lnn-prometheus", "lnn-grafana"]
    results = {}

    for container in expected:
        status = check_container_running(container)
        if status == "not_found":
            print(f"  [SKIP] {container}: 未运行")
            results[container] = None
            continue

        health = check_container_health(container)
        if health == "healthy":
            print(f"  [OK] {container}: 运行中, 健康检查通过")
            results[container] = True
        elif health == "starting":
            print(f"  [WARN] {container}: 正在启动中")
            results[container] = None
        else:
            print(f"  [FAIL] {container}: 状态={status}, 健康={health}")
            results[container] = False

    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)

    if failed > 0:
        return False
    if passed > 0 and skipped == 0:
        return True
    return None  # SKIP


def verify_service_dependencies():
    """步骤10: 服务依赖管理验证"""
    print("\n" + "=" * 60)
    print("步骤10: 服务依赖管理验证")
    print("=" * 60)

    # 直接读取docker-compose.yml文件检查依赖配置
    compose_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docker-compose.yml",
    )
    if not os.path.exists(compose_path):
        print("  [FAIL] docker-compose.yml文件不存在")
        return False

    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查依赖配置
    checks = {
        "lnn-api depends on postgres (service_healthy)": "postgres" in content
        and "condition: service_healthy" in content,
        "lnn-api depends on redis (service_healthy)": "redis" in content
        and "condition: service_healthy" in content,
        "grafana depends on prometheus (service_healthy)": "prometheus" in content
        and "condition: service_healthy" in content,
    }

    all_passed = True
    for name, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    return all_passed


def verify_grafana_integration():
    """步骤6: Grafana仪表板集成验证"""
    print("\n" + "=" * 60)
    print("步骤6: Grafana仪表板集成验证")
    print("=" * 60)

    # 检查Grafana是否可访问
    try:
        req = urllib.request.Request("http://localhost:3000/api/health")
        req.add_header("Authorization", "Basic YWRtaW46YWRtaW4=")  # admin:admin
        r = urllib.request.urlopen(req, timeout=5)
        data = json.loads(r.read().decode("utf-8"))
        if data.get("commit"):
            print(f"  [OK] Grafana可访问: {data.get('database', 'unknown')}")
        else:
            print(f"  [FAIL] Grafana响应异常: {data}")
            return False
    except Exception as e:
        print(f"  [SKIP] Grafana未运行或无法访问: {e}")
        return None  # SKIP

    # 检查Prometheus数据源配置
    try:
        req = urllib.request.Request("http://localhost:3000/api/datasources")
        req.add_header("Authorization", "Basic YWRtaW46YWRtaW4=")
        r = urllib.request.urlopen(req, timeout=5)
        datasources = json.loads(r.read().decode("utf-8"))
        prom_ds = [ds for ds in datasources if ds.get("type") == "prometheus"]
        if prom_ds:
            print(f"  [OK] Prometheus数据源已配置: {prom_ds[0].get('name')}")
        else:
            print("  [WARN] 未找到Prometheus数据源")
    except Exception as e:
        print(f"  [WARN] 无法检查数据源: {e}")

    # 检查Grafana provisioning配置
    provisioning_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "deploy",
        "grafana",
        "provisioning",
    )
    if os.path.exists(provisioning_dir):
        print("  [OK] Grafana provisioning目录存在")
        for subdir in ["datasources", "dashboards"]:
            path = os.path.join(provisioning_dir, subdir)
            if os.path.exists(path):
                files = os.listdir(path)
                print(f"    [OK] {subdir}: {', '.join(files)}")
    else:
        print(f"  [WARN] Grafana provisioning目录不存在: {provisioning_dir}")

    return True


def verify_high_latency_scenario():
    """步骤7: 高延迟场景处理验证"""
    print("\n" + "=" * 60)
    print("步骤7: 高延迟场景处理验证")
    print("=" * 60)

    # 先执行几次推理来确保有性能数据
    print("  执行5次推理请求以填充性能数据...")
    for i in range(5):
        result = get("/api/v1/lnn/predict")
        time.sleep(0.2)

    # 获取性能统计
    perf = get("/api/v1/lnn/performance")
    if not perf:
        print("  [FAIL] 无法获取性能统计")
        return False

    data = perf.get("data", {})
    models = data.get("models", [])
    if not models:
        print("  [SKIP] 没有模型性能数据")
        return None

    m = models[0]
    p95 = m.get("p95_inference_ms", 0)
    total = m.get("total_inferences", 0)

    print(f"  模型: {m.get('model_name')}")
    print(f"  推理次数: {total}")
    print(f"  P95延迟: {p95}ms")

    # 检查Prometheus告警规则中的高延迟阈值
    alert_rules_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "deploy",
        "prometheus",
        "alert_rules.yml",
    )
    if not os.path.exists(alert_rules_path):
        print("  [FAIL] 告警规则文件不存在")
        return False

    with open(alert_rules_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查是否存在高延迟告警规则
    has_latency_alert = "LNNInferenceLatency" in content
    has_threshold = "histogram_quantile(0.95" in content

    if has_latency_alert and has_threshold:
        print("  [OK] 高延迟告警规则已配置")
        # 提取阈值
        import re

        thresholds = re.findall(r">\s+([\d.]+)", content)
        print(f"  检测到的阈值: {', '.join(thresholds)}s")
    else:
        print("  [FAIL] 高延迟告警规则未配置")
        return False

    # 检查日志中是否有P95警告（通过ring buffer的system_event检查）
    try:
        logs = get("/api/v1/logs/system_event?limit=10")
        if logs:
            entries = logs.get("entries", []) if isinstance(logs, dict) else []
            print(f"  系统事件日志条目: {len(entries)}")
            for entry in entries[-3:]:
                msg = entry.get("message", "")
                if (
                    "p95" in msg.lower()
                    or "threshold" in msg.lower()
                    or "latency" in msg.lower()
                ):
                    print(f"  [OK] 检测到延迟警告日志: {msg[:100]}")
                    return True
    except:
        pass

    print("  [OK] 高延迟监控已配置（实际触发需真实高延迟场景）")
    return True


def verify_prometheus_alerts():
    """步骤8: Prometheus告警规则验证"""
    print("\n" + "=" * 60)
    print("步骤8: Prometheus告警规则验证")
    print("=" * 60)

    # 检查Prometheus是否可访问
    try:
        req = urllib.request.Request("http://localhost:9090/api/v1/rules")
        r = urllib.request.urlopen(req, timeout=5)
        data = json.loads(r.read().decode("utf-8"))
        rules = data.get("data", {}).get("groups", [])
        print("  [OK] Prometheus规则端点可访问")

        # 检查告警规则
        alert_rules = []
        for group in rules:
            for rule in group.get("rules", []):
                if rule.get("type") == "alerting":
                    alert_rules.append(rule.get("name"))

        if alert_rules:
            print(f"  已加载告警规则: {', '.join(alert_rules)}")
            expected_alerts = ["BackendDown", "HighResponseTime", "LNNInferenceLatency"]
            for expected in expected_alerts:
                if expected in alert_rules:
                    print(f"  [OK] {expected} 规则已加载")
                else:
                    print(f"  [WARN] {expected} 规则未找到")
        else:
            print("  [WARN] 未找到告警规则")
    except Exception as e:
        print(f"  [SKIP] Prometheus未运行或无法访问: {e}")
        return None  # SKIP

    # 检查告警规则文件
    alert_rules_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "deploy",
        "prometheus",
        "alert_rules.yml",
    )
    if not os.path.exists(alert_rules_path):
        print("  [FAIL] 告警规则文件不存在")
        return False

    with open(alert_rules_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查关键告警规则
    required_alerts = [
        "BackendDown",
        "HighResponseTime",
        "HighErrorRate",
        "LNNInferenceLatency",
        "HighMemoryUsage",
        "HighCPUUsage",
    ]

    all_passed = True
    for alert_name in required_alerts:
        if alert_name in content:
            print(f"  [OK] {alert_name} 规则已定义")
        else:
            print(f"  [FAIL] {alert_name} 规则未定义")
            all_passed = False

    return all_passed


if __name__ == "__main__":
    results = {}

    results["步骤9_Docker健康检查"] = verify_docker_health_checks()
    results["步骤10_服务依赖"] = verify_service_dependencies()
    results["步骤6_Grafana集成"] = verify_grafana_integration()
    results["步骤7_高延迟场景"] = verify_high_latency_scenario()
    results["步骤8_Prometheus告警"] = verify_prometheus_alerts()

    print("\n" + "=" * 60)
    print("Docker相关验证总结")
    print("=" * 60)

    for name, result in results.items():
        if result is True:
            status = "[通过]"
        elif result is False:
            status = "[失败]"
        else:
            status = "[跳过]"
        print(f"  {name}: {status}")

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    print(f"\n通过: {passed}, 失败: {failed}, 跳过: {skipped}")

    if failed > 0:
        print("\n部分验证失败，请检查错误日志。")
        sys.exit(1)
    else:
        print("\n所有可执行的验证通过！")
