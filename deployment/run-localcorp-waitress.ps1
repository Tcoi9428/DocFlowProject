param(
    [Parameter(Mandatory = $true)]
    [string]$DbPassword,

    [Parameter(Mandatory = $true)]
    [string]$SecretKey,

    [string]$MediaRoot = "S:\DocFlow\data\media",
    [string]$StaticRoot = "S:\DocFlow\data\staticfiles",
    [string]$DbDriver = "ODBC Driver 18 for SQL Server",
    [string]$PythonExe = "",
    [int]$Port = 8010,

    [string]$BaseUrl = "http://10.110.53.17:8010",
    [string]$EmailHost = "smtp.yandex.ru",
    [int]$EmailPort = 465,
    [string]$EmailUser = "",
    [string]$EmailPassword = "",
    [ValidateSet("ssl", "tls", "none")]
    [string]$EmailSecurity = "ssl",
    [string]$DefaultFromEmail = "DocFlow <docflow-notify@yandex.ru>"
)

$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
$installationRoot = Split-Path -Parent $appRoot
Set-Location -LiteralPath $appRoot

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $pythonCandidates = @(
        (Join-Path $installationRoot "venv\Scripts\python.exe"),
        (Join-Path $appRoot ".venv\Scripts\python.exe"),
        (Join-Path $appRoot "venv\Scripts\python.exe")
    )

    $PythonExe = $pythonCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1

    if ([string]::IsNullOrWhiteSpace($PythonExe)) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            throw "Python was not found. Expected '$installationRoot\venv\Scripts\python.exe' or pass -PythonExe explicitly."
        }
        $PythonExe = $pythonCommand.Source
    }
}

Write-Host "Using Python: $PythonExe" -ForegroundColor Cyan

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

$installedDrivers = @(Get-OdbcDriver | Select-Object -ExpandProperty Name)
if ($installedDrivers -notcontains $DbDriver) {
    Write-Host "Installed ODBC drivers:" -ForegroundColor Yellow
    $installedDrivers | Where-Object { $_ -like "*SQL*" } | ForEach-Object { Write-Host " - $_" }
    throw "ODBC driver '$DbDriver' is not installed. Install it or pass the exact installed driver name with -DbDriver."
}

. "$PSScriptRoot\set-localcorp-env.ps1" `
    -DbPassword $DbPassword `
    -SecretKey $SecretKey `
    -MediaRoot $MediaRoot `
    -StaticRoot $StaticRoot `
    -DbDriver $DbDriver `
    -BaseUrl $BaseUrl `
    -EmailHost $EmailHost `
    -EmailPort $EmailPort `
    -EmailUser $EmailUser `
    -EmailPassword $EmailPassword `
    -EmailSecurity $EmailSecurity `
    -DefaultFromEmail $DefaultFromEmail

New-Item -ItemType Directory -Force -Path $env:DOCFLOW_MEDIA_ROOT | Out-Null
New-Item -ItemType Directory -Force -Path $env:DOCFLOW_STATIC_ROOT | Out-Null

Invoke-Checked $PythonExe manage.py check
Invoke-Checked $PythonExe manage.py migrate
Invoke-Checked $PythonExe manage.py collectstatic --noinput

Invoke-Checked $PythonExe -m waitress --listen="0.0.0.0:$Port" docflow_project.wsgi:application
