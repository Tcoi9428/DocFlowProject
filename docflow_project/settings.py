import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    value = os.getenv(name)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv(
    "DOCFLOW_SECRET_KEY",
    "django-insecure-gc$*6f!s&(cb5^x#s7*8+bwpl@r%$4z(*c@&%$bxk#1hl65#ki",
)

DEBUG = env_bool("DOCFLOW_DEBUG", True)

ALLOWED_HOSTS = env_list("DOCFLOW_ALLOWED_HOSTS", ["127.0.0.1", "localhost"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env_list("DOCFLOW_CSRF_TRUSTED_ORIGINS")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "documents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "docflow_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "documents.context_processors.notification_context",
            ],
        },
    },
]

WSGI_APPLICATION = "docflow_project.wsgi.application"


if os.getenv("DOCFLOW_DB_ENGINE", "sqlite").lower() == "mssql":
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.getenv("DOCFLOW_DB_NAME", "DocFlow"),
            "USER": os.getenv("DOCFLOW_DB_USER", ""),
            "PASSWORD": os.getenv("DOCFLOW_DB_PASSWORD", ""),
            "HOST": os.getenv("DOCFLOW_DB_HOST", "localhost"),
            "PORT": os.getenv("DOCFLOW_DB_PORT", "1433"),
            "OPTIONS": {
                "driver": os.getenv("DOCFLOW_DB_DRIVER", "ODBC Driver 18 for SQL Server"),
                "extra_params": os.getenv("DOCFLOW_DB_EXTRA_PARAMS", "TrustServerCertificate=yes"),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("DOCFLOW_SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "documents.password_validation.LatinLettersAndDigitsPasswordValidator",
    },
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Asia/Yekaterinburg"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = Path(os.getenv("DOCFLOW_STATIC_ROOT", BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("DOCFLOW_MEDIA_ROOT", BASE_DIR / "media"))
MAX_UPLOAD_SIZE = int(os.getenv("DOCFLOW_MAX_UPLOAD_SIZE", 20 * 1024 * 1024))


LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "documents:my_documents"
LOGOUT_REDIRECT_URL = "login"

EMAIL_BACKEND = os.getenv("DOCFLOW_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("DOCFLOW_EMAIL_HOST", "smtp.yandex.ru")
EMAIL_PORT = int(os.getenv("DOCFLOW_EMAIL_PORT", "465"))
EMAIL_HOST_USER = os.getenv("DOCFLOW_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DOCFLOW_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_SSL = env_bool("DOCFLOW_EMAIL_USE_SSL", True)
EMAIL_USE_TLS = env_bool("DOCFLOW_EMAIL_USE_TLS", False)
EMAIL_TIMEOUT = int(os.getenv("DOCFLOW_EMAIL_TIMEOUT", "15"))
DEFAULT_FROM_EMAIL = os.getenv("DOCFLOW_DEFAULT_FROM_EMAIL", "DocFlow <docflow-notify@yandex.ru>")

DOCFLOW_BASE_URL = os.getenv("DOCFLOW_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DOCFLOW_EMAIL_SEND_IMMEDIATELY = env_bool("DOCFLOW_EMAIL_SEND_IMMEDIATELY", False)
DOCFLOW_EMAIL_MAX_ATTEMPTS = int(os.getenv("DOCFLOW_EMAIL_MAX_ATTEMPTS", "5"))

if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("DOCFLOW_SESSION_COOKIE_SECURE", False)
    CSRF_COOKIE_SECURE = env_bool("DOCFLOW_CSRF_COOKIE_SECURE", False)
    SECURE_CONTENT_TYPE_NOSNIFF = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
