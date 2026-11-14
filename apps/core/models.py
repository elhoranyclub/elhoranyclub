"""
Core models.

SiteSettings is a singleton holding every configurable identity/contact/social
detail so the center name, colors and phone numbers are NEVER hard-coded in
templates. It can be edited from the admin (Phase 8) or via `seed_core`.
"""
from __future__ import annotations

import logging

from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class TimeStampedModel(models.Model):
    """Abstract base: created/updated timestamps on every table."""

    created_at = models.DateTimeField(_("تاريخ الإنشاء"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("تاريخ التحديث"), auto_now=True)

    class Meta:
        abstract = True


class SiteSettings(TimeStampedModel):
    """Singleton row (pk=1) with the public identity of the center."""

    name_ar = models.CharField(_("اسم المركز (عربي)"), max_length=120, default="مركز شباب الحوراني")
    name_en = models.CharField(_("اسم المركز (إنجليزي)"), max_length=120, default="Al-Hourani Youth Sports Center")
    tagline_ar = models.CharField(_("الشعار النصي (عربي)"), max_length=180, default="نحو جيل رياضي مبدع", blank=True)
    tagline_en = models.CharField(_("الشعار النصي (إنجليزي)"), max_length=180, default="Towards a creative athletic generation", blank=True)

    logo = models.ImageField(_("الشعار"), upload_to="documents/logos/", blank=True, null=True)

    phone = models.CharField(_("الهاتف"), max_length=20, default="01272833888", blank=True)
    whatsapp = models.CharField(_("واتساب"), max_length=20, default="01272833888", blank=True)
    email = models.EmailField(_("البريد الإلكتروني"), default="info@hourani-sports.eg", blank=True)
    address_ar = models.CharField(_("العنوان (عربي)"), max_length=255, default="الحوراني — مركز ومدينة فارسكور — محافظة دمياط", blank=True)
    address_en = models.CharField(_("العنوان (إنجليزي)"), max_length=255, default="Al-Hourani — Faraskour Center & City — Damietta Governorate", blank=True)
    map_embed_url = models.URLField(_("رابط خريطة Google (embed)"), blank=True)

    working_hours_ar = models.CharField(_("مواعيد العمل (عربي)"), max_length=180, default="يوميًا ٧ صباحًا – ١٠ مساءً", blank=True)
    working_hours_en = models.CharField(_("مواعيد العمل (إنجليزي)"), max_length=180, default="Daily 7:00 AM – 10:00 PM", blank=True)

    facebook_url = models.URLField(_("فيسبوك"), blank=True)
    instagram_url = models.URLField(_("إنستجرام"), blank=True)
    youtube_url = models.URLField(_("يوتيوب"), blank=True)
    tiktok_url = models.URLField(_("تيك توك"), blank=True)

    # Brand tokens — overridable so identity can change without a deploy
    primary_color = models.CharField(_("اللون الأساسي (كحلي)"), max_length=7, default="#0e2a47")
    gold_color = models.CharField(_("اللون الذهبي"), max_length=7, default="#d4af37")
    green_color = models.CharField(_("اللون الأخضر"), max_length=7, default="#146b3a")

    # Top announcement ticker (breaking news / offers)
    announcement_enabled = models.BooleanField(_("تفعيل شريط الإعلان العاجل"), default=False)
    announcement_text_ar = models.CharField(_("نص الإعلان (عربي)"), max_length=255, blank=True)
    announcement_text_en = models.CharField(_("نص الإعلان (إنجليزي)"), max_length=255, blank=True)

    # سياسة الإلغاء للأنشطة (بالساعة قبل الموعد)
    event_cancel_cutoff_hours = models.PositiveSmallIntegerField(_("آخر موعد لإلغاء تسجيل النشاط (ساعة)"), default=24)

    # Master switch: allow/disable public self-registration (e.g. during maintenance)
    is_registration_open = models.BooleanField(_("التسجيل العام متاح"), default=True)

    # Fine applied on every renewal when a member lets the subscription lapse 1+ year from the last payment
    late_fine_percent = models.DecimalField(_("نسبة غرامة التأخير بعد سنة (٪)"), max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name = _("إعدادات الموقع")
        verbose_name_plural = _("إعدادات الموقع")

    def save(self, *args, **kwargs):
        # Enforce singleton behaviour
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None  # singleton cannot be deleted

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return self.name_ar


from .audit import AuditLog  # noqa: F401,F811 — registered for migrations
