"""
Base settings — مركز شباب الحوراني
Shared across dev & prod. Environment-specific overrides live in dev.py / prod.py.
Secrets are read from .env (see .env.example). Nothing secret is hard-coded here.
"""
from pathlib import Path

import environ
import mimetypes

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# بيخلي WhiteNoise يقدّم ملف الـ PWA manifest بنوعه الصح (application/manifest+json)
# — من غير كده المتصفح بيconsiderه ملف عادي وبيتجاهل تثبيت التطبيق.
mimetypes.add_type("application/manifest+json", ".webmanifest")

# رمز تحقق Google Search Console (بيتحط في <head> تلقائيًا)
GOOGLE_SITE_VERIFICATION = env("GOOGLE_SITE_VERIFICATION", default="")

# الدفع الإلكتروني المباشر (كارت عبر Paymob) — مقفول لحد ما تتفعّل بوابة حقيقية
ONLINE_PAYMENT_ENABLED = env.bool("ONLINE_PAYMENT_ENABLED", default=False)

# Django 6.0 هيتغيّر سلوك التحقق من الروابط — نفترض https (أأمن) ونكتم التحذير
FORMS_URLFIELD_ASSUME_HTTPS = True

# ---------------------------------------------------------------- Core
SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-key-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
# Django 4+ يشترط إن كل أصل يكون بصيغة http:// أو https:// — بنتجاهل أي قيمة ناقصة
# (زي «*») بدل ما يفشل البناء كله بسببها.
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in env.list("CSRF_TRUSTED_ORIGINS", default=[])
    if origin.strip().startswith(("http://", "https://"))
]

# ------------------------------------------------------------- Apps
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "django_htmx",
    "cloudinary",
    "cloudinary_storage",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.memberships",
    "apps.news",
    "apps.events",
    "apps.tournaments",
    "apps.courses",
    "apps.trips",
    "apps.payments",
    "apps.notifications",
    "apps.gallery",
    "apps.pages",
    "apps.api",
    "apps.dashboard",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.site_settings",
            ],
        },
    },
]

# --------------------------------------------------------- Database
# Reads DATABASE_URL from .env — switching SQLite → Postgres (Neon)
# requires NO code change. Neon cold-start note: keep CONN_MAX_AGE modest
# (300–600) and set connect_timeout; use the pooled (-pooler) host with
# sslmode=require on Neon.
DATABASES = {"default": env.db_url("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=0 if DEBUG else 600)
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 10

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------ Custom user
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------- i18n (RTL/LTR)
LANGUAGE_CODE = "ar"
LANGUAGES = [
    ("ar", "العربية"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# --------------------------------------------------------- Static/media
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_CLOUDINARY = env.bool("USE_CLOUDINARY", default=False)
if USE_CLOUDINARY:
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME", default=""),
        "API_KEY": env("CLOUDINARY_API_KEY", default=""),
        "API_SECRET": env("CLOUDINARY_API_SECRET", default=""),
    }
    # Folders on Cloudinary: news/, events/, members/, receipts/, documents/, gallery/
    DEFAULT_FILE_BACKEND = "cloudinary_storage.storage.MediaCloudinaryStorage"
    STORAGES = {
        "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }

# Max upload sizes: images 5MB, PDFs 10MB (enforced in validators, Phase 1+)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ------------------------------------------------------------- Email
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@hourani-sports.eg")

# -------------------------------------------------------- Integrations
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="mock")  # mock | paymob | fawry
NOTIFICATIONS_PROVIDER = env("NOTIFICATIONS_PROVIDER", default="console")  # console | whatsapp | sms
OTP_PROVIDER = env("OTP_PROVIDER", default="console")  # console | whatsapp | sms
MOCK_WEBHOOK_SECRET = env("MOCK_WEBHOOK_SECRET", default="mock-secret")
# Public origin of the deployed site — used for absolute asset URLs inside HTML emails (logo…)
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="https://hourani-sports.eg")
DEFAULT_CENTER_NAME_AR = env("DEFAULT_CENTER_NAME_AR", default="مركز شباب الحوراني")
DEFAULT_CENTER_NAME_EN = env("DEFAULT_CENTER_NAME_EN", default="Al-Hourani Youth Sports Center")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# ------------------------------------------------------------ Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG" if DEBUG else "INFO", "propagate": False},
    },
}
