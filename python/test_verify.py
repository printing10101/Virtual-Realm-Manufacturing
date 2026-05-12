import urllib.request
import json
import time

TOKEN = '4e45821e-08e4-4fc3-83a6-74c1fb24fe3a'

def get(path):
    req = urllib.request.Request(
        f'http://localhost:8000{path}',
        headers={'Authorization': f'Bearer {TOKEN}'}
    )
    r = urllib.request.urlopen(req)
    return json.loads(r.read().decode())

def post(path, data):
    req = urllib.request.Request(
        f'http://localhost:8000{path}',
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {TOKEN}'}
    )
    r = urllib.request.urlopen(req)
    return json.loads(r.read().decode())

print("=" * 60)
print("步骤1: 后端推理功能与日志完整性检测")
print("=" * 60)

print("\n>>> 1a. 健康检查")
resp = get('/api/health/ping')
print(f"    状态: {resp}")

print("\n>>> 1b. 获取模型列表")
resp = get('/api/v1/lnn/models')
models = resp.get('data', resp) if isinstance(resp, dict) else resp
if isinstance(models, list):
    print(f"    已注册模型: {models}")
else:
    print(f"    模型列表: {json.dumps(models, indent=2, ensure_ascii=False)}")

if isinstance(models, list) and len(models) > 0:
    test_model = models[0]
    if isinstance(test_model, dict):
        test_model = test_model.get('name', models[0])
    print(f"\n>>> 1c. 使用模型 '{test_model}' 执行10次推理")
else:
    test_model = 'cutting_force'
    print(f"\n>>> 1c. 使用模型 '{test_model}' 执行10次推理")

results = []
inference_data = [10.0, 20.0, 15.0, 2000.0, 0.5]

for i in range(10):
    try:
        resp = post('/api/v1/lnn/predict', {
            'model_name': test_model,
            'input_data': inference_data,
            'return_confidence': True
        })
        results.append(resp)
        print(f"    第{i+1}次: 成功 - 推理耗时: {resp.get('data', {}).get('inference_time', 'N/A')}ms")
    except Exception as e:
        print(f"    第{i+1}次: 失败 - {e}")

print(f"\n>>> 1d. 验证推理日志 (GET /api/v1/logs/ai_inference)")
try:
    resp = get('/api/v1/logs/ai_inference?limit=20')
    entries = resp.get('data', {}).get('entries', [])
    print(f"    返回条目数: {len(entries)}")
    for e in entries[:3]:
        print(f"    - [{e.get('timestamp', 'N/A')}] {e.get('message', 'N/A')}")
except Exception as e:
    print(f"    查询失败: {e}")

print("\n>>> 1e. 验证请求日志 (GET /api/v1/logs/request?limit=20)")
try:
    resp = get('/api/v1/logs/request?limit=20')
    entries = resp.get('data', {}).get('entries', [])
    print(f"    返回条目数: {len(entries)}")
    for e in entries[:5]:
        print(f"    - [{e.get('timestamp', 'N/A')}] {e.get('message', 'N/A')}")
except Exception as e:
    print(f"    查询失败: {e}")

print("\n>>> 1f. 验证日志统计 (GET /api/v1/logs/stats)")
try:
    resp = get('/api/v1/logs/stats')
    print(f"    统计: {json.dumps(resp.get('data', resp), indent=2, ensure_ascii=False)}")
except Exception as e:
    print(f"    查询失败: {e}")

print("\n" + "=" * 60)
print("步骤2: 性能统计接口验证")
print("=" * 60)
print("\n>>> GET /api/v1/lnn/performance")
try:
    resp = get('/api/v1/lnn/performance')
    print(json.dumps(resp, indent=2, ensure_ascii=False)[:2000])
except Exception as e:
    print(f"    查询失败: {e}")

print("\n" + "=" * 60)
print("步骤5: Prometheus指标暴露验证")
print("=" * 60)
print("\n>>> GET /api/metrics")
try:
    r = urllib.request.urlopen('http://localhost:8000/api/metrics')
    metrics_text = r.read().decode()
    lines = metrics_text.strip().split('\n')
    print(f"    总行数: {len(lines)}")
    # 检查关键指标
    key_metrics = [
        'lnn_inference_duration_seconds',
        'lnn_model_load_duration_seconds',
        'lnn_prediction_count',
        'agent_requests_total',
        'sidecar_uptime_seconds',
        'ring_buffer_entries',
        'http_request_duration_seconds',
        'http_requests_total',
        'process_resident_memory_bytes',
        'process_cpu_percent',
    ]
    print("\n    关键指标检查:")
    for km in key_metrics:
        found = any(km in line for line in lines)
        status = '[OK]' if found else '[MISS]'
        print(f"      [{status}] {km}")
    
    print("\n    前30行:")
    for line in lines[:30]:
        print(f"      {line}")
except Exception as e:
    print(f"    查询失败: {e}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
