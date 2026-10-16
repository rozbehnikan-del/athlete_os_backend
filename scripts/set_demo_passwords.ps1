$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $Root ".venv"
$EnvPath = Join-Path $Root ".env"
$ActivatePath = Join-Path $VenvPath "Scripts\Activate.ps1"
$ScriptPath = Join-Path $Root "scripts\set_demo_passwords.py"

Set-Location $Root

if (-not (Test-Path $VenvPath)) {
    Write-Error ".venv is missing. Run .\scripts\setup_local.ps1 first."
}

if (-not (Test-Path $EnvPath)) {
    Write-Error ".env is missing. Copy .env.example to .env and fill DB credentials locally."
}

& $ActivatePath
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python was not found in the virtual environment. Run .\scripts\setup_local.ps1 first."
}

python $ScriptPath --confirm-demo-passwords
