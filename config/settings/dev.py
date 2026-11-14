"""Development settings — DEBUG on, console email, relaxed hosts."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
# في التطوير: console افتراضيًا، لكن يقبل EMAIL_BACKEND صريح من الـ env (مثلاً Brevo للتجربة)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
