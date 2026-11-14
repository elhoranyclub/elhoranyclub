"""Test guard — tests must never send real emails through Brevo/SMTP.

django-environ reads .env with overwrite=False, so values already in
os.environ win. Force the console email backend for the whole test suite.
"""
import os

os.environ.setdefault("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
