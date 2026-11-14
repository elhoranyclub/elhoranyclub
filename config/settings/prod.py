"""Production settings — HTTPS enforced, secure cookies, HSTS, Sentry (optional)."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# Cookies & HTTPS
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # HTMX needs to read it via {% csrf_token %}
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Use the same (non-manifest) WhiteNoise backend as base — the deploy guide /
# Procfile run `collectstatic` via manage.py which defaults to DEV settings
# (no manifest is generated). Manifest storage would then 500 every {% static %}.
# CompressedStaticFilesStorage serves the same files with sensible defaults.
STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
}

# Optional Sentry — only if SENTRY_DSN is set
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1, send_default_pii=False)
