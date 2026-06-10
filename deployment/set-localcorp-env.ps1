param(
    [Parameter(Mandatory = $true)]
    [string]$DbPassword,

    [Parameter(Mandatory = $true)]
    [string]$SecretKey,

    [string]$MediaRoot = "S:\DocFlow\data\media",
    [string]$StaticRoot = "S:\DocFlow\data\staticfiles"
)

$env:DOCFLOW_DEBUG = "false"
$env:DOCFLOW_SECRET_KEY = $SecretKey
$env:DOCFLOW_ALLOWED_HOSTS = "127.0.0.1,localhost,10.110.53.17"
$env:DOCFLOW_CSRF_TRUSTED_ORIGINS = "http://10.110.53.17:8010"

$env:DOCFLOW_DB_ENGINE = "mssql"
$env:DOCFLOW_DB_NAME = "DocflowApplicationDB"
$env:DOCFLOW_DB_USER = "DocFlowUser"
$env:DOCFLOW_DB_PASSWORD = $DbPassword
$env:DOCFLOW_DB_HOST = "10.110.53.17"
$env:DOCFLOW_DB_PORT = "1433"
$env:DOCFLOW_DB_DRIVER = "ODBC Driver 18 for SQL Server"
$env:DOCFLOW_DB_EXTRA_PARAMS = "TrustServerCertificate=yes"

$env:DOCFLOW_MEDIA_ROOT = $MediaRoot
$env:DOCFLOW_STATIC_ROOT = $StaticRoot

$env:DOCFLOW_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
$env:DOCFLOW_DEFAULT_FROM_EMAIL = "docflow@company.local"
