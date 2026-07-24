param(
    [Parameter(Mandatory = $true)]
    [string]$DbPassword,

    [Parameter(Mandatory = $true)]
    [string]$SecretKey,

    [Parameter(Mandatory = $true)]
    [string]$EmailPassword,

    [string]$EmailUser = "docflow-notify@yandex.ru",
    [string]$EmailHost = "smtp.yandex.ru",
    [int]$EmailPort = 465,
    [ValidateSet("ssl", "tls", "none")]
    [string]$EmailSecurity = "ssl",
    [string]$DefaultFromEmail = "DocFlow <docflow-notify@yandex.ru>",
    [string]$BaseUrl = "http://10.110.53.17:8010",
    [string]$MediaRoot = "S:\DocFlow\data\media",
    [string]$StaticRoot = "S:\DocFlow\data\staticfiles",
    [string]$DbDriver = "ODBC Driver 18 for SQL Server",
    [string]$PythonExe = "",
    [int]$Limit = 50
)

$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
$installationRoot = Split-Path -Parent $appRoot
Set-Location -LiteralPath $appRoot

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = @(
        (Join-Path $installationRoot "venv\Scripts\python.exe"),
        (Join-Path $appRoot ".venv\Scripts\python.exe"),
        (Join-Path $appRoot "venv\Scripts\python.exe")
    ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    throw "Python virtual environment was not found. Pass -PythonExe explicitly."
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

& $PythonExe manage.py send_notification_emails --limit $Limit
if ($LASTEXITCODE -ne 0) {
    throw "Email queue command failed with exit code $LASTEXITCODE."
}
