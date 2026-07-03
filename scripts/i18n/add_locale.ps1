param(
    [string]$File,
    [string]$Namespace
)

# Read the file content
$content = [System.IO.File]::ReadAllText($File, [System.Text.Encoding]::UTF8)

# Find the last occurrence of "\n}" (the closing brace of the export default object)
$lastBraceIndex = $content.LastIndexOf("`n}")

if ($lastBraceIndex -lt 0) {
    Write-Host "ERROR: Could not find closing brace in $File"
    exit 1
}

# Insert the new namespace before the closing brace
$newContent = $content.Substring(0, $lastBraceIndex + 1) + $Namespace + "`n}"

# Write the file back
[System.IO.File]::WriteAllText($File, $newContent, (New-Object System.Text.UTF8Encoding $true))

Write-Host "SUCCESS: Added namespace to $File"
