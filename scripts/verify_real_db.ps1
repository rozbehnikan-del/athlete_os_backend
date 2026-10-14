$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $Root ".venv"
$EnvPath = Join-Path $Root ".env"
$ActivatePath = Join-Path $VenvPath "Scripts\Activate.ps1"
$SmokeTestPath = Join-Path $Root "scripts\real_db_smoke_test.py"

Set-Location $Root
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $Root
} else {
    "$Root;$env:PYTHONPATH"
}

if (-not (Test-Path $VenvPath)) {
    Write-Error ".venv is missing. Run .\scripts\setup_local.ps1 first."
}

if (-not (Test-Path $EnvPath)) {
    Write-Error "Copy .env.example to .env and fill DB credentials locally."
}

& $ActivatePath
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python was not found in the virtual environment. Run .\scripts\setup_local.ps1 first."
}
python $SmokeTestPath
