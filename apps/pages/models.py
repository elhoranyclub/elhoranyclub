"""Pages — مرافق، مجلس إدارة، أسئلة شائعة، رسائل التواصل."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Facility(TimeStampedModel):
    name_ar = models.CharField(_("الاسم (عربي)"), max_length=120)
    name_en = models.CharField(_("الاسم (إنجليزي)"), max_length=120, blank=True)
    description = models.CharField(_("الوصف"), max_length=300, blank=True)
    image = models.ImageField(_("الصورة"), upload_to="documents/facilities/", blank=True, null=True)
    icon = models.CharField(_("مفتاح الأيقونة"), max_length=30, default="trophy", help_text=_("مثل: swim, dumbbell, ball, table"))
    hours = models.CharField(_("مواعيد"), max_length=120, blank=True, default="يوميًا ٧ ص – ١٠ م")
    order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("مرفق")
        verbose_name_plural = _("المرافق")
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.name_ar


class BoardMember(TimeStampedModel):
    name_ar = models.CharField(_("الاسم (عربي)"), max_length=120)
    name_en = models.CharField(_("الاسم (إنجليزي)"), max_length=120, blank=True)
    role_ar = models.CharField(_("المنصب (عربي)"), max_length=120)
    role_en = models.CharField(_("المنصب (إنجليزي)"), max_length=120, blank=True)
    image = models.ImageField(_("الصورة"), upload_to="documents/board/", blank=True, null=True)
    order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("عضو مجلس إدارة")
        verbose_name_plural = _("أعضاء مجلس الإدارة")
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.name_ar} — {self.role_ar}"


class FAQ(TimeStampedModel):
    question_ar = models.CharField(_("السؤال (عربي)"), max_length=300)
    question_en = models.CharField(_("السؤال (إنجليزي)"), max_length=300, blank=True)
    answer_ar = models.TextField(_("الإجابة (عربي)"))
    answer_en = models.TextField(_("الإجابة (إنجليزي)"), blank=True)
    order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("سؤال شائع")
        verbose_name_plural = _("الأسئلة الشائعة")
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.question_ar


class ContactMessage(TimeStampedModel):
    name = models.CharField(_("الاسم"), max_length=120)
    phone = models.CharField(_("الموبايل"), max_length=15)
    email = models.EmailField(_("البريد (اختياري)"), blank=True)
    subject = models.CharField(_("الموضوع"), max_length=200)
    message = models.TextField(_("الرسالة"), max_length=2000)
    is_read = models.BooleanField(_("مقروءة"), default=False)

    class Meta:
        verbose_name = _("رسالة تواصل")
        verbose_name_plural = _("رسائل التواصل")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_read", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.name}: {self.subject}"
