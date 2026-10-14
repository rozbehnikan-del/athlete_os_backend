$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Show-JsonResult($Label, $Result) {
    Write-Host ""
    Write-Host $Label
    $Result | ConvertTo-Json -Depth 10
}

$Health = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"
Show-JsonResult "Health:" $Health

$Ready = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/ready"
Show-JsonResult "Readiness:" $Ready

$Today = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/v1/athletes/me/workouts/today"
Show-JsonResult "Today's workout:" $Today

if ($null -ne $Today.data) {
    $ExerciseCount = $Today.data.exercises.Count
    $SetCount = 0
    foreach ($Exercise in $Today.data.exercises) {
        $SetCount += $Exercise.sets.Count
    }

    Write-Host ""
    Write-Host "Workout summary:"
    Write-Host "Title: $($Today.data.title)"
    Write-Host "Category: $($Today.data.category)"
    Write-Host "Focus: $($Today.data.focus)"
    Write-Host "Exercises: $ExerciseCount"
    Write-Host "Sets: $SetCount"
}
