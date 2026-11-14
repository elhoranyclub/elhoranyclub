"""
Notification services — rendering + dispatch with channel preferences.
المزود عبر NOTIFICATIONS_PROVIDER في .env: console (افتراضي) | whatsapp | sms.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _

from .models import Notification, NotificationPreference, NotificationTemplate

logger = logging.getLogger(__name__)


def _render(template: NotificationTemplate, context: dict[str, Any], key: str) -> str:
    text = getattr(template, key)
    for name, value in context.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def _safe_format(text: str, context: dict[str, Any]) -> str:
    try:
        return text.format(**{k: str(v) for k, v in context.items()})
    except (KeyError, ValueError, IndexError):
        return text


def notify_user(*, user, type: str, code: str | None, context: dict | None = None, subject: str = "", body: str = "", action_url: str = "") -> list[Notification]:
    """ينشئ إشعارات حسب تفضيلات المستخدم + يرسل القنوات الخارجية (console حاليًا)."""
    context = context or {}
    created: list[Notification] = []

    if code:
        template = NotificationTemplate.objects.filter(code=code, is_active=True).first()
        if template:
            subject = _render(template, context, "subject_ar")
            body = _render(template, context, "body_ar")
        else:
            logger.info("Notification template missing: %s (fallback subject/body)", code)
    subject = _safe_format(subject or _("إشعار من المركز"), context)
    body = _safe_format(body or subject, context)

    prefs, _prefs_created = NotificationPreference.objects.get_or_create(user=user)

    def _make(channel):
        return Notification.objects.create(user=user, type=type, channel=channel, subject=subject, body=body, action_url=action_url or "")

    if prefs.in_app:
        created.append(_make(Notification.Channel.IN_APP))
    if prefs.email and user.email:
        try:
            from apps.core.emails import send_branded_email

            send_branded_email(
                subject=subject,
                template="emails/notification_email.html",
                context={"title": subject, "body": body, "action_url": action_url,
                         "action_label": "فتح التفاصيل",
                         "fallback_text": f"{subject}\n\n{body}\n\n{action_url}"},
                to=[user.email],
                fail_silently=True,
            )
            created.append(_make(Notification.Channel.EMAIL))
        except Exception as exc:
            logger.warning("email send failed for user %s: %s", user.id, exc)
    if prefs.whatsapp or prefs.sms:
        provider = getattr(settings, "NOTIFICATIONS_PROVIDER", "console")
        if provider == "console":
            logger.warning("=== WHATSAPP (console) -> %s : %s — %s ===", user.phone, subject, body)
            created.append(_make(Notification.Channel.WHATSAPP if prefs.whatsapp else Notification.Channel.SMS))
    return created


def unread_count(user) -> int:
    return Notification.objects.filter(user=user, read=False).count()


def mark_all_read(user) -> int:
    return Notification.objects.filter(user=user, read=False).update(read=True)
