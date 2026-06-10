param(
    [Parameter(Mandatory = $true)]
    [string]$DbPassword,

    [Parameter(Mandatory = $true)]
    [string]$SecretKey,

    [string]$MediaRoot = "S:\DocFlow\data\media",
    [string]$StaticRoot = "S:\DocFlow\data\staticfiles",
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\set-localcorp-env.ps1" `
    -DbPassword $DbPassword `
    -SecretKey $SecretKey `
    -MediaRoot $MediaRoot `
    -StaticRoot $StaticRoot

New-Item -ItemType Directory -Force -Path $env:DOCFLOW_MEDIA_ROOT | Out-Null
New-Item -ItemType Directory -Force -Path $env:DOCFLOW_STATIC_ROOT | Out-Null

python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput

python -m waitress --listen="0.0.0.0:$Port" docflow_project.wsgi:application
