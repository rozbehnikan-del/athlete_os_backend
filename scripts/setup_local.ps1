$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-PythonCommand {
    foreach ($Command in @("python", "python3", "py")) {
        if (Get-Command $Command -ErrorAction SilentlyContinue) {
            return $Command
        }
    }
    Write-Error "Python was not found. Install Python 3.12+ and ensure it is available on PATH."
}

$Python = Get-PythonCommand

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host "Now edit .env and enter your real PostgreSQL connection details."
