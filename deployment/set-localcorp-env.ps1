param(
    [Parameter(Mandatory = $true)]
    [string]$DbPassword,

    [Parameter(Mandatory = $true)]
    [string]$SecretKey,

    [string]$MediaRoot = "S:\DocFlow\data\media",
    [string]$StaticRoot = "S:\DocFlow\data\staticfiles",
    [string]$DbDriver = "ODBC Driver 18 for SQL Server",

    [string]$BaseUrl = "http://10.110.53.17:8010",
    [string]$EmailHost = "smtp.yandex.ru",
    [int]$EmailPort = 465,
    [string]$EmailUser = "",
    [string]$EmailPassword = "",
    [ValidateSet("ssl", "tls", "none")]
    [string]$EmailSecurity = "ssl",
    [string]$DefaultFromEmail = "DocFlow <docflow-notify@yandex.ru>"
)

$env:DOCFLOW_DEBUG = "false"
$env:DOCFLOW_SECRET_KEY = $SecretKey
$env:DOCFLOW_ALLOWED_HOSTS = "127.0.0.1,localhost,10.110.53.17"
$env:DOCFLOW_CSRF_TRUSTED_ORIGINS = "http://10.110.53.17:8010"

$env:DOCFLOW_DB_ENGINE = "mssql"
$env:DOCFLOW_DB_NAME = "DocflowApplicationDB"
$env:DOCFLOW_DB_USER = "FlowUser"
$env:DOCFLOW_DB_PASSWORD = $DbPassword
$env:DOCFLOW_DB_HOST = "10.110.53.17"
$env:DOCFLOW_DB_PORT = "1433"
$env:DOCFLOW_DB_DRIVER = $DbDriver
$env:DOCFLOW_DB_EXTRA_PARAMS = "TrustServerCertificate=yes"

$env:DOCFLOW_MEDIA_ROOT = $MediaRoot
$env:DOCFLOW_STATIC_ROOT = $StaticRoot

$env:DOCFLOW_BASE_URL = $BaseUrl.TrimEnd("/")
$env:DOCFLOW_EMAIL_HOST = $EmailHost
$env:DOCFLOW_EMAIL_PORT = $EmailPort.ToString()
$env:DOCFLOW_EMAIL_HOST_USER = $EmailUser
$env:DOCFLOW_EMAIL_HOST_PASSWORD = $EmailPassword
$env:DOCFLOW_DEFAULT_FROM_EMAIL = $DefaultFromEmail
$env:DOCFLOW_EMAIL_TIMEOUT = "15"
$env:DOCFLOW_EMAIL_MAX_ATTEMPTS = "5"

if ([string]::IsNullOrWhiteSpace($EmailUser) -or [string]::IsNullOrWhiteSpace($EmailPassword)) {
    $env:DOCFLOW_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    $env:DOCFLOW_EMAIL_SEND_IMMEDIATELY = "false"
} else {
    $env:DOCFLOW_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    $env:DOCFLOW_EMAIL_SEND_IMMEDIATELY = "true"
}

$env:DOCFLOW_EMAIL_USE_SSL = ($EmailSecurity -eq "ssl").ToString().ToLowerInvariant()
$env:DOCFLOW_EMAIL_USE_TLS = ($EmailSecurity -eq "tls").ToString().ToLowerInvariant()
