param([string], [string])
 = [char]34
 = [System.IO.File]::ReadAllText(, [System.Text.Encoding]::UTF8)
 = [System.IO.File]::ReadAllText(, [System.Text.Encoding]::UTF8)
 = .LastIndexOf([char]10 + [string][char]125)
if ( -lt 0) { Write-Host 'ERROR: No closing brace'; exit 1 }
 = .Substring(0,  + 1) +  + [char]10 + [char]125
[System.IO.File]::WriteAllText(, , (New-Object System.Text.UTF8Encoding True))
Write-Host 'SUCCESS'