$ErrorActionPreference = 'Stop'

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Define all replacement rules
$replacements = @{
    'app\.core\.security\b'                = 'app.auth.security'
    'app\.core\.permissions\b'             = 'app.auth.permissions'
    'app\.core\.middleware\.unified_auth\b'  = 'app.auth.unified_auth'
    'app\.core\.middleware\.security_headers_asgi\b' = 'app.auth.security_headers_asgi'

    'app\.core\.task_system\b'             = 'app.tasks.task_system'
    'app\.core\.task_manager\b'             = 'app.tasks.task_manager'
    'app\.core\.task_checkout\b'            = 'app.tasks.task_checkout'
    'app\.core\.worker_process\b'           = 'app.tasks.worker_process'
    'app\.core\.execution_lock\b'           = 'app.tasks.execution_lock'
    'app\.core\.execution\b'                = 'app.tasks.execution'

    'app\.core\.plugin_system\b'            = 'app.plugins.plugin_system'
    'app\.core\.plugin_worker\b'            = 'app.plugins.plugin_worker'
    'app\.core\.skill_loader\b'             = 'app.plugins.skill_loader'
    'app\.core\.skill_marketplace\b'        = 'app.plugins.skill_marketplace'

    'app\.core\.budget_enforcer\b'          = 'app.budget.budget_enforcer'
    'app\.core\.cost_tracker\b'             = 'app.budget.cost_tracker'
    'app\.core\.approval_workflow\b'        = 'app.budget.approval_workflow'
    'app\.core\.budget\b'                   = 'app.budget.budget'

    'app\.core\.goal_alignment\b'           = 'app.goals.goal_alignment'
    'app\.core\.goal_chain_store\b'         = 'app.goals.goal_chain_store'
}

# Get all Python files
$files = Get-ChildItem -Path "app","tests" -Recurse -Include "*.py" -File

$totalChanged = 0
foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    if ([string]::IsNullOrEmpty($content)) { continue }
    $changed = $false

    foreach ($pattern in $replacements.Keys) {
        $newText = $replacements[$pattern]
        $regex = [regex]$pattern
        if ($regex.IsMatch($content)) {
            $content = $regex.Replace($content, $newText)
            $changed = $true
        }
    }

    if ($changed) {
        Set-Content -Path $file.FullName -Value $content -Encoding UTF8 -NoNewline
        Write-Host "Updated: $($file.FullName.Replace($ScriptDir, ''))"
        $totalChanged++
    }
}

Write-Host ""
Write-Host "Total files changed: $totalChanged"
