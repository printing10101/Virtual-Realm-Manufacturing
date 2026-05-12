$jobId = "lnn_training-ea5323933d1b"
$uri = "http://localhost:8000/api/v1/jobs/$jobId/stream"
$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromSeconds(10)
$request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $uri)
$request.Headers.Add("Accept", "text/event-stream")

try {
    $startTime = Get-Date
    $response = $client.SendAsync($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).Result
    $statusCode = [int]$response.StatusCode
    $elapsed = ((Get-Date) - $startTime).TotalSeconds
    Write-Host "Status: $statusCode, Connect time: $elapsed s"
    
    if ($statusCode -eq 200) {
        $stream = $response.Content.ReadAsStreamAsync().Result
        $reader = [System.IO.StreamReader]::new($stream)
        $count = 0
        $deadline = (Get-Date).AddSeconds(8)
        while ((Get-Date) -lt $deadline -and $count -lt 15) {
            $line = $reader.ReadLine()
            if ($line) {
                $count++
                Write-Host "[$count] $line"
            }
        }
        $reader.Close()
    }
    $response.Dispose()
} catch {
    Write-Host "ERROR: $_"
}
