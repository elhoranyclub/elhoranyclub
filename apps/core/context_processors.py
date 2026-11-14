"""Expose site identity to every template — never hard-code it there."""
from __future__ import annotations

import logging
from types import SimpleNamespace

from django.conf import settings

logger = logging.getLogger(__name__)

_FALLBACK = SimpleNamespace(
    name_ar=getattr(settings, "DEFAULT_CENTER_NAME_AR", "مركز شباب الحوراني"),
    name_en=getattr(settings, "DEFAULT_CENTER_NAME_EN", "Al-Hourani Youth Sports Center"),
    tagline_ar="نحو جيل رياضي مبدع",
    tagline_en="Towards a creative athletic generation",
    phone="01272833888",
    whatsapp="01272833888",
    email="info@hourani-sports.eg",
    address_ar="الحوراني — مركز ومدينة فارسكور — محافظة دمياط",
    address_en="Al-Hourani — Faraskour Center & City — Damietta Governorate",
    map_embed_url="",
    working_hours_ar="يوميًا ٧ صباحًا – ١٠ مساءً",
    working_hours_en="Daily 7:00 AM – 10:00 PM",
    facebook_url="",
    instagram_url="",
    youtube_url="",
    tiktok_url="",
    primary_color="#0e2a47",
    gold_color="#d4af37",
    green_color="#146b3a",
    announcement_enabled=False,
    announcement_text_ar="",
    announcement_text_en="",
    is_registration_open=True,
    logo=None,
)


def site_settings(request):
    """Return ``site_settings`` (DB row or env fallback) and localized name."""
    lang = getattr(request, "LANGUAGE_CODE", "ar")
    try:
        from apps.core.models import SiteSettings

        s = SiteSettings.load()
    except Exception as exc:  # DB not migrated yet / table missing
        logger.debug("site_settings fallback (DB not ready): %s", exc)
        s = _FALLBACK

    site_name = s.name_ar if lang == "ar" else s.name_en
    tagline = s.tagline_ar if lang == "ar" else s.tagline_en

    unread = 0
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        try:
            from apps.notifications.services import unread_count

            unread = unread_count(user)
        except Exception as exc:
            logger.debug("unread_count fallback: %s", exc)

    return {
        "site_settings": s,
        "site_name": site_name,
        "site_tagline": tagline,
        "BACKEND_IS_AR": lang == "ar",
        "notifications_unread": unread,
    }
