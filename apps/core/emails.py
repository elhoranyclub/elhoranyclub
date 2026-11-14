"""HTML email renderer + sender — لإيميل بطابع النادي.

القوالب في templates/emails/:
- base_email.html/.txt: الإطار (header + footer + الهوية)
- otp_email.html/.txt: كود التحقق / التفعيل
- notification_email.html/.txt: أي إشعار عام بمحتوى حر + زرار اختياري
"""
from __future__ import annotations

import logging
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _site_context() -> dict:
    """الهوية (اسم النادي/الشراط/مبدع…) — من قاعدة البيانات لو متاحة وإلا القيم الافتراضية."""
    try:
        from apps.core.models import SiteSettings

        s = SiteSettings.load()
    except Exception:  # DB not migrated yet / table missing
        from apps.core.context_processors import _FALLBACK

        s = _FALLBACK

    def _get(name, default=""):
        return getattr(s, name, default) or default

    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return {
        "site_name": _get("name_ar", "مركز شباب الحوراني"),
        "site_tagline": _get("tagline_ar", ""),
        "site_phone": _get("phone", ""),
        "site_email": _get("email", ""),
        "site_address": _get("address_ar", ""),
        "site_hours": _get("working_hours_ar", ""),
        "facebook_url": _get("facebook_url", ""),
        "instagram_url": _get("instagram_url", ""),
        "youtube_url": _get("youtube_url", ""),
        "tiktok_url": _get("tiktok_url", ""),
        # CID: attached inline by send_branded_email → guaranteed visible in every client
        "logo_src": "cid:hourani-logo",
        "brand_navy": _get("primary_color", "#0e2a47"),
        "brand_gold": _get("gold_color", "#d4af37"),
        "brand_green": _get("green_color", "#146b3a"),
        "site_url": base,
    }


def render_email(template: str, context: dict | None = None) -> tuple[str, str]:
    """بيرجع (html, text) — text من نسخة .txt من نفس القالب لو موجودة."""
    ctx = {**_site_context(), **(context or {})}
    html = render_to_string(template, ctx)
    txt_template = template[: -len(".html")] + ".txt" if template.endswith(".html") else None
    text = ""
    if txt_template:
        try:
            text = render_to_string(txt_template, ctx)
        except Exception:
            text = ctx.get("fallback_text", "")
    return html, text


def send_branded_email(*, subject: str, template: str, context: dict | None, to: list[str], fail_silently: bool = False) -> int:
    html, text = render_email(template, context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text or html,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    msg.attach_alternative(html, "text/html")
    try:
        logo_path = Path(settings.BASE_DIR) / "static" / "icons" / "icon-192.png"
        with open(logo_path, "rb") as fh:
            logo = MIMEImage(fh.read(), _subtype="png")
        logo.add_header("Content-ID", "<hourani-logo>")
        logo.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(logo)
    except Exception:
        logger.warning("branded email: inline logo attachment failed — continuing without it", exc_info=True)
    try:
        return msg.send(fail_silently=fail_silently)
    except Exception:
        logger.exception("branded email failed (template=%s to=%s)", template, to)
        if fail_silently:
            return 0
        raise
