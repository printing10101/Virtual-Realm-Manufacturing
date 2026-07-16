# 使用 WinHTTP COM 对象下载 torch CPU wheel（绕过 WinSock 损坏）
# WinHTTP 是独立于 WinSock 的网络栈，诊断已确认其完全可用

param(
    [string]$OutDir = "C:\Users\Lenovo\Desktop\torch_wheels",
    [string]$PythonTag = "cp313",
    [string]$TorchVersion = "2.6.0"
)

$ErrorActionPreference = "Stop"

Write-Host "=== WinHTTP torch wheel 下载器 ==="
Write-Host ("Python tag: " + $PythonTag)
Write-Host ("Torch version: " + $TorchVersion)
Write-Host ("输出目录: " + $OutDir)

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
    Write-Host ("已创建输出目录: " + $OutDir)
}

# === 步骤 1: 测试 WinHTTP 连通性 ===
Write-Host ""
Write-Host "=== [1] 测试 WinHTTP 连通性 ==="
try {
    $testReq = New-Object -ComObject WinHttp.WinHttpRequest.5.1
    $testReq.Open("GET", "https://download.pytorch.org/whl/cpu/torch/", $false)
    $testReq.SetTimeouts(30000, 30000, 30000, 30000)
    $testReq.Send()
    Write-Host ("状态码: " + $testReq.Status)
    Write-Host ("状态文本: " + $testReq.StatusText)
    $body = $testReq.ResponseText
    Write-Host ("响应长度: " + $body.Length + " 字符")
} catch {
    Write-Host ("WinHTTP 测试失败: " + $_.Exception.Message)
    Write-Host "无法继续，请检查网络"
    exit 1
}

# === 步骤 2: 从 HTML 中解析 wheel 文件名 ===
Write-Host ""
Write-Host "=== [2] 解析 wheel 文件列表 ==="
$pattern = 'href="([^"]*win_amd64\.whl)"'
$matches = [regex]::Matches($body, $pattern)
Write-Host ("找到 " + $matches.Count + " 个 win_amd64 wheel 文件")

# 筛选目标 wheel
$targetPattern = "torch-" + $TorchVersion + ".*" + $PythonTag + ".*win_amd64"
$candidates = @()
foreach ($m in $matches) {
    $fname = $m.Groups[1].Value
    if ($fname -match $targetPattern) {
        $candidates += $fname
        Write-Host ("  候选: " + $fname)
    }
}

if ($candidates.Count -eq 0) {
    Write-Host ("未找到匹配的 wheel: " + $targetPattern)
    Write-Host "可用 wheel（前 20 个）:"
    $matches | Select-Object -First 20 | ForEach-Object {
        Write-Host ("  " + $_.Groups[1].Value)
    }
    exit 2
}

# 选择第一个候选
$wheelFile = $candidates[0]
Write-Host ("选择下载: " + $wheelFile)

# === 步骤 3: 下载 wheel 文件 ===
Write-Host ""
Write-Host "=== [3] 下载 wheel 文件 ==="
$downloadUrl = "https://download.pytorch.org/whl/cpu/" + $wheelFile
$outFile = Join-Path $OutDir $wheelFile
Write-Host ("下载 URL: " + $downloadUrl)
Write-Host ("保存路径: " + $outFile)

try {
    $req = New-Object -ComObject WinHttp.WinHttpRequest.5.1
    $req.Open("GET", $downloadUrl, $false)
    $req.SetTimeouts(60000, 60000, 300000, 300000)  # 5 分钟接收超时
    $req.Send()
    Write-Host ("HTTP 状态: " + $req.Status + " " + $req.StatusText)

    if ($req.Status -eq 200) {
        # 保存到文件
        $bodyBytes = $req.ResponseBody
        $stream = New-Object -ComObject ADODB.Stream
        $stream.Type = 1  # adTypeBinary
        $stream.Open()
        $stream.Write($bodyBytes)
        $stream.SaveToFile($outFile, 2)  # adSaveCreateOverWrite
        $stream.Close()

        $fileInfo = Get-Item $outFile
        $sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
        Write-Host ("下载完成: " + $fileInfo.Name)
        Write-Host ("文件大小: " + $sizeMB + " MB")
        Write-Host ("SHA256: " + (Get-FileHash $outFile -Algorithm SHA256).Hash)
        Write-Host ("保存路径: " + $outFile)
    } else {
        Write-Host ("下载失败，HTTP 状态: " + $req.Status)
        exit 3
    }
} catch {
    Write-Host ("下载异常: " + $_.Exception.Message)
    exit 4
}

Write-Host ""
Write-Host "=== 下载完成 ==="
Write-Host ("wheel 路径: " + $outFile)
Write-Host ("下一步: pip install """ + $outFile + """")
