# 测试 WinHTTP COM 对象能否连通 PyTorch 下载站点
$ErrorActionPreference = "Stop"

Write-Host "=== WinHTTP 连通性测试 ==="

try {
    $r = New-Object -ComObject WinHttp.WinHttpRequest.5.1
    $r.Open("GET", "https://download.pytorch.org/whl/cpu/torch/", $false)
    $r.SetTimeouts(30000, 30000, 30000, 30000)
    $r.Send()
    Write-Host ("Status: " + $r.Status + " " + $r.StatusText)

    $body = $r.ResponseText
    Write-Host ("Body length: " + $body.Length)

    # 解析 wheel 文件列表
    $pattern = 'href="([^"]*win_amd64\.whl)"'
    $matches = [regex]::Matches($body, $pattern)
    Write-Host ("Win_amd64 wheels found: " + $matches.Count)
    Write-Host ""
    Write-Host "可用 wheel（前 40 个）:"
    $matches | Select-Object -First 40 | ForEach-Object {
        Write-Host ("  " + $_.Groups[1].Value)
    }

    # 筛选 cp313 wheel
    Write-Host ""
    Write-Host "=== cp313 候选 ==="
    $cp313 = $matches | Where-Object { $_.Groups[1].Value -match "cp313.*win_amd64" }
    Write-Host ("cp313 wheel 数量: " + $cp313.Count)
    $cp313 | ForEach-Object { Write-Host ("  " + $_.Groups[1].Value) }

} catch {
    Write-Host ("FAIL: " + $_.Exception.Message)
    exit 1
}

Write-Host ""
Write-Host "=== 测试完成 ==="
