# Obsidian 記事を同期して GitHub に公開する
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Write-StepResult {
    param(
        [string]$Step,
        [bool]$Success,
        [string]$Detail = ""
    )
    $status = if ($Success) { "OK" } else { "FAILED" }
    $color = if ($Success) { "Green" } else { "Red" }
    Write-Host "[$status] $Step" -ForegroundColor $color
    if ($Detail) {
        Write-Host "       $Detail"
    }
}

Write-Host ""
Write-Host "=== publish.ps1 ===" -ForegroundColor Cyan
Write-Host ""

# 1. sync_diary.py
Write-Host "[1/4] python scripts/sync_diary.py"
try {
    python scripts/sync_diary.py
    if ($LASTEXITCODE -ne 0) {
        throw "exit code $LASTEXITCODE"
    }
    Write-StepResult -Step "sync_diary.py" -Success $true
}
catch {
    Write-StepResult -Step "sync_diary.py" -Success $false -Detail $_.Exception.Message
    exit 1
}

# 2. git add
Write-Host ""
Write-Host "[2/4] git add ."
try {
    git add .
    if ($LASTEXITCODE -ne 0) {
        throw "exit code $LASTEXITCODE"
    }
    Write-StepResult -Step "git add" -Success $true
}
catch {
    Write-StepResult -Step "git add" -Success $false -Detail $_.Exception.Message
    exit 1
}

# 3. git commit（変更がなければスキップ）
Write-Host ""
Write-Host "[3/4] git commit"
git diff --cached --quiet
$hasStaged = $LASTEXITCODE -ne 0
if ($hasStaged) {
    try {
        git commit -m "update posts"
        if ($LASTEXITCODE -ne 0) {
            throw "exit code $LASTEXITCODE"
        }
        Write-StepResult -Step "git commit" -Success $true -Detail "update posts"
    }
    catch {
        Write-StepResult -Step "git commit" -Success $false -Detail $_.Exception.Message
        exit 1
    }
}
else {
    Write-StepResult -Step "git commit" -Success $true -Detail "no changes (skipped)"
}

# 4. git push
Write-Host ""
Write-Host "[4/4] git push"
try {
    git push
    if ($LASTEXITCODE -ne 0) {
        throw "exit code $LASTEXITCODE"
    }
    Write-StepResult -Step "git push" -Success $true
}
catch {
    Write-StepResult -Step "git push" -Success $false -Detail $_.Exception.Message
    exit 1
}

Write-Host ""
Write-Host "=== done ===" -ForegroundColor Cyan
Write-Host ""
