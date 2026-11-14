"""
OTP delivery abstraction.
Development: ConsoleOTPProvider logs the code (and stores nothing sensitive).
Email: EmailOTPProvider sends the code to the user's registered email via SMTP (free — Gmail SMTP).
Production: set OTP_PROVIDER=email in .env after filling the EMAIL_*_Gmail values.
"""
from __future__ import annotations

import abc
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class OTPProvider(abc.ABC):
    @abc.abstractmethod
    def send(self, phone: str, code: str, purpose: str | None = None) -> bool:
        """Deliver the code. Return True on success."""


def mask_email(email: str) -> str:
    """an***@gmail.com — لعرض الإيميل بدون كشفه كاملًا."""
    local, _, domain = email.partition("@")
    if not domain:
        return email
    if len(local) <= 2:
        return local[0] + "***@" + domain
    return local[:2] + "***" + local[-1] + "@" + domain


class EmailOTPProvider(OTPProvider):
    """يبعت رمز التحقق على إيميل المستخدم المسجّل بهذا الرقم (مجاني عبر Gmail SMTP)."""

    def send(self, phone: str, code: str, purpose: str | None = None) -> bool:
        from django.conf import settings

        from apps.accounts.models import OTP, User
        from apps.core.emails import send_branded_email

        user = User.objects.filter(phone=phone).first()
        email = (user.email or "").strip() if user else ""
        if not email:
            logger.warning("EmailOTP: no email on file for phone %s", phone)
            return False
        name = (user.first_name or "").strip()
        try:
            send_branded_email(
                subject=f"رمز التحقق — {getattr(settings, 'DEFAULT_CENTER_NAME_AR', 'مركز شباب الحوراني')}",
                template="emails/otp_email.html",
                context={"code": code, "name": name, "ttl_minutes": OTP.TTL_MINUTES, "purpose": purpose or "register", "fallback_text": f"رمز التحقق: {code}"},
                to=[email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("EmailOTP: failed to send verification email to %s", mask_email(email))
            return False
        logger.info("EmailOTP: sent code to %s for phone %s", mask_email(email), phone)
        return True


class ConsoleOTPProvider(OTPProvider):
    """Dev/test provider — logs the code to the console. Never use in prod."""

    def send(self, phone: str, code: str, purpose: str | None = None) -> bool:
        logger.warning("=== OTP (console provider) >> %s : %s ===", phone, code)
        return True


def get_provider() -> OTPProvider:
    name = getattr(settings, "OTP_PROVIDER", "console")
    providers = {
        "console": ConsoleOTPProvider,
        "email": EmailOTPProvider,  # يبعت الكود على إيميل المستخدم — مجاني عبر Gmail SMTP
        # "whatsapp": WhatsAppOTPProvider,  # WhatsApp Cloud API — مدفوع (~$0.0036 للكود) + Meta onboarding
        # "sms": SmsOTPProvider,
    }
    cls = providers.get(name, ConsoleOTPProvider)
    return cls()


def send_otp(phone: str, purpose: str) -> bool:
    """Issue a fresh OTP and deliver it. Returns False when rate-limited."""
    from django.utils import timezone

    from apps.accounts.models import OTP

    # Rate limit: max 5 OTPs per phone per hour
    recent = OTP.objects.filter(phone=phone, created_at__gte=timezone.now() - timezone.timedelta(hours=1)).count()
    if recent >= 5:
        logger.warning("OTP rate-limited for %s", phone)
        return False
    _otp, code = OTP.issue(phone, purpose)
    return get_provider().send(phone, code, purpose=purpose)
