param(
    [Parameter(Mandatory = $true)]
    [string]$DbPassword,

    [Parameter(Mandatory = $true)]
    [string]$SecretKey,

    [string]$MediaRoot = "S:\DocFlow\data\media",
    [string]$StaticRoot = "S:\DocFlow\data\staticfiles",
    [string]$DbDriver = "ODBC Driver 18 for SQL Server",
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

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
    -DbDriver $DbDriver

New-Item -ItemType Directory -Force -Path $env:DOCFLOW_MEDIA_ROOT | Out-Null
New-Item -ItemType Directory -Force -Path $env:DOCFLOW_STATIC_ROOT | Out-Null

Invoke-Checked python manage.py check
Invoke-Checked python manage.py migrate
Invoke-Checked python manage.py collectstatic --noinput

Invoke-Checked python -m waitress --listen="0.0.0.0:$Port" docflow_project.wsgi:application
