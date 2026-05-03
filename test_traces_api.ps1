# 创建测试任务
$body = @{
    task_type = "process_generation"
    params = @{
        material = "45钢"
        part_type = "轴类"
    }
} | ConvertTo-Json -Depth 3

$response = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/v1/tasks" -Method Post -Body $body -ContentType "application/json"
Write-Host "任务创建响应:"
$response | ConvertTo-Json -Depth 5

$taskId = $response.data.task_id
Write-Host "`n任务ID: $taskId"

# 等待几秒让任务执行
Start-Sleep -Seconds 3

# 获取任务traces
Write-Host "`n获取任务Traces:"
$tracesResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/v1/traces/$taskId" -Method Get
$tracesResponse | ConvertTo-Json -Depth 5

# 获取SOTA指标
Write-Host "`n获取SOTA指标:"
$sotaResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/v1/traces/$taskId/sota" -Method Get
$sotaResponse | ConvertTo-Json -Depth 5

# 获取Mermaid DAG图
Write-Host "`n获取Mermaid DAG图:"
$mermaidResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/v1/traces/$taskId/mermaid" -Method Get
$mermaidResponse | ConvertTo-Json -Depth 5
