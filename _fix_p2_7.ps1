# P2-7 批量修复脚本：datetime.now() → datetime.now(timezone.utc)
# 仅替换 isoformat() / timestamp() 调用，保留 strftime()（用于文件名/显示）

$ErrorActionPreference = "Stop"

$files = @(
    "engineering\python\app\ai\lnn\inference\predictor.py",
    "engineering\python\app\ai\lnn\postprocessing.py",
    "engineering\python\app\api\v1\lnn\routes_prediction.py",
    "engineering\python\app\api\v1\lnn\services.py",
    "engineering\python\app\api\v1\sse.py",
    "engineering\python\app\api\v1\user_sovereignty.py",
    "engineering\python\app\dnc\dnc_manager.py",
    "engineering\python\app\dnc\mtconnect_client.py",
    "engineering\python\app\dnc\opcu_client.py",
    "engineering\python\app\dnc\unified_adapter.py",
    "engineering\python\app\dreaming\apply_rules.py",
    "engineering\python\app\dreaming\cli.py",
    "engineering\python\app\dreaming\effectiveness_metrics.py",
    "engineering\python\app\dreaming\reflector.py",
    "engineering\python\app\dreaming\rule_synthesizer.py",
    "engineering\python\app\dreaming\rule_validator.py",
    "engineering\python\app\dreaming\report_generator.py",
    "engineering\python\app\knowledge_graph\extractor\review.py",
    "engineering\python\app\pipelines\feedback_loop.py",
    "engineering\python\app\plugins\world_model\training\fusion_trainer.py",
    "engineering\python\app\rag\evaluation.py",
    "engineering\python\app\research_bridge\data_collector.py",
    "engineering\python\app\sidecar\sidecar_lifecycle.py",
    "engineering\python\app\tasks\execution.py",
    "engineering\python\app\tasks\task_checkout.py",
    "engineering\python\app\tasks\task_system.py",
    "engineering\python\app\services\experience_store.py",
    "engineering\python\app\agent\orchestrator.py",
    "engineering\python\app\validation\geometric_validator.py"
)

$root = "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
$summary = @()

foreach ($rel in $files) {
    $path = Join-Path $root $rel
    if (-not (Test-Path $path)) {
        $summary += "SKIP (not found): $rel"
        continue
    }

    $content = Get-Content -Path $path -Raw -Encoding UTF8
    $original = $content

    # 1. 替换 isoformat() 调用（aware datetime）
    $content = $content -replace 'datetime\.now\(\)\.isoformat\(\)', 'datetime.now(timezone.utc).isoformat()'

    # 2. 替换 _datetime.now().isoformat() (services.py 别名)
    $content = $content -replace '_datetime\.now\(\)\.isoformat\(\)', '_datetime.now(_timezone.utc).isoformat()'

    # 3. 替换 timestamp() 调用
    $content = $content -replace 'datetime\.now\(\)\.timestamp\(\)', 'datetime.now(timezone.utc).timestamp()'

    # 4. 替换比较和算术运算中的 datetime.now()
    # 仅在已知安全场景替换：datetime.now() < / > / - / +
    $content = $content -replace 'datetime\.now\(\)\s*([<>+\-])', 'datetime.now(timezone.utc) $1'
    $content = $content -replace '([<>+\-])\s*datetime\.now\(\)', '$1 datetime.now(timezone.utc)'

    # 5. 添加 timezone 到 import 语句（如果尚未导入）
    # 模式 A: from datetime import datetime  →  from datetime import datetime, timezone
    if ($content -match 'from datetime import datetime\s*$' -and $content -notmatch 'from datetime import.*timezone') {
        $content = $content -replace 'from datetime import datetime(?!\s*,)', 'from datetime import datetime, timezone'
    }
    # 模式 B: from datetime import datetime, timedelta  →  ..., timezone
    if ($content -match 'from datetime import datetime, timedelta\s*$' -and $content -notmatch 'from datetime import.*timezone') {
        $content = $content -replace 'from datetime import datetime, timedelta(?!\s*,)', 'from datetime import datetime, timedelta, timezone'
    }
    # 模式 C: from datetime import datetime, date  →  ..., timezone
    if ($content -match 'from datetime import datetime, date\s*$' -and $content -notmatch 'from datetime import.*timezone') {
        $content = $content -replace 'from datetime import datetime, date(?!\s*,)', 'from datetime import datetime, date, timezone'
    }
    # 模式 D: services.py 特有 from datetime import datetime as _datetime
    if ($content -match 'from datetime import datetime as _datetime\s*$' -and $content -notmatch '_timezone') {
        $content = $content -replace 'from datetime import datetime as _datetime(?!\s*,)', 'from datetime import datetime as _datetime, timezone as _timezone'
    }

    if ($content -ne $original) {
        [System.IO.File]::WriteAllText($path, $content, [System.Text.Encoding]::UTF8)
        $summary += "MODIFIED: $rel"
    } else {
        $summary += "NO-CHANGE: $rel"
    }
}

Write-Host "=== P2-7 修复汇总 ==="
$summary | ForEach-Object { Write-Host $_ }
Write-Host ""
Write-Host "=== 残留 datetime.now() 调用检查 ==="
foreach ($rel in $files) {
    $path = Join-Path $root $rel
    if (Test-Path $path) {
        $matches = findstr /N "datetime.now()" $path 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "--- $rel ---"
            $matches | ForEach-Object { Write-Host $_ }
        }
    }
}
Write-Host "=== 检查完成 ==="
