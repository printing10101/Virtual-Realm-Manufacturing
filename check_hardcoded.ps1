$count = 0
Get-ChildItem -Path 'src\views','src\components' -Recurse -Include *.vue -ErrorAction SilentlyContinue | ForEach-Object {
  $file = $_.FullName
  $idx = 0
  Get-Content $file -Encoding UTF8 | ForEach-Object {
    $idx++
    $line = $_
    if ($line -match '[\u4e00-\u9fff]') {
      if ($line -notmatch '\$t\(') {
        $count++
        Write-Output ('{0}:{1}: {2}' -f $file, $idx, $line.Trim())
      }
    }
  }
}
Write-Output ('TOTAL_LINES={0}' -f $count)
Write-Output 'DONE'
