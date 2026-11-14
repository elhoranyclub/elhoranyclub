"""
Notifications — مركز شباب الحوراني
إشعارات داخل التطبيق + إيميل (اختياري) + واتساب/SMS عبر abstraction layer (console للتطوير).
"""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class NotificationTemplate(TimeStampedModel):
    """قوالب رسائل قابلة للتعديل من لوحة التحكم — {name} و{ref} و{days} إلخ."""

    code = models.CharField(_("الكود"), max_length=60, unique=True)
    subject_ar = models.CharField(_("العنوان (عربي)"), max_length=200)
    body_ar = models.TextField(_("النص (عربي)"))
    subject_en = models.CharField(_("العنوان (إنجليزي)"), max_length=200, blank=True)
    body_en = models.TextField(_("النص (إنجليزي)"), blank=True)
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("قالب إشعار")
        verbose_name_plural = _("قوالب الإشعارات")

    def __str__(self) -> str:
        return self.code


class Notification(TimeStampedModel):
    class Channel(models.TextChoices):
        IN_APP = "in_app", _("داخل التطبيق")
        EMAIL = "email", _("بريد إلكتروني")
        WHATSAPP = "whatsapp", _("واتساب")
        SMS = "sms", _("رسالة نصية")

    class Type(models.TextChoices):
        WELCOME = "welcome", _("ترحيب")
        MEMBERSHIP_EXPIRING = "membership_expiring", _("قرب انتهاء الاشتراك")
        PAYMENT_CONFIRMED = "payment_confirmed", _("تأكيد الدفع")
        PAYMENT_RECEIVED = "payment_received", _("استلمنا إيصالك")
        EVENT_REMINDER = "event_reminder", _("تذكير نشاط")
        TOURNAMENT_UPDATE = "tournament_update", _("تحديث بطولة")
        COURSE_COMPLETED = "course_completed", _("إتمام دورة")
        TRIP_CONFIRMED = "trip_confirmed", _("تأكيد رحلة")
        SYSTEM = "system", _("نظام")

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications", verbose_name=_("المستخدم"))
    type = models.CharField(_("النوع"), max_length=30, choices=Type.choices, default=Type.SYSTEM, db_index=True)
    channel = models.CharField(_("القناة"), max_length=10, choices=Channel.choices, default=Channel.IN_APP)
    subject = models.CharField(_("العنوان"), max_length=250)
    body = models.TextField(_("النص"))
    action_url = models.CharField(_("رابط الإجراء (اختياري)"), max_length=300, blank=True)
    read = models.BooleanField(_("مقروء"), default=False, db_index=True)
    sent_at = models.DateTimeField(_("أُرسل في"), auto_now_add=True)

    class Meta:
        verbose_name = _("إشعار")
        verbose_name_plural = _("الإشعارات")
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["user", "read", "-sent_at"])]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.subject}"


class NotificationPreference(TimeStampedModel):
    """تفضيلات كل قناة للعضو — ينسحب عليها الإرسال التلقائي."""

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="notification_preference", verbose_name=_("المستخدم"))
    in_app = models.BooleanField(_("داخل التطبيق"), default=True)
    email = models.BooleanField(_("بريد إلكتروني"), default=True)
    whatsapp = models.BooleanField(_("واتساب"), default=True)
    sms = models.BooleanField(_("رسائل نصية"), default=False)

    class Meta:
        verbose_name = _("تفضيلات الإشعارات")
        verbose_name_plural = _("تفضيلات الإشعارات")

    def __str__(self) -> str:
        return str(self.user_id)
