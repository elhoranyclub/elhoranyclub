"""Events — أنشطة المركز مع التسجيل وقائمة الانتظار عند الاكتمال."""
from __future__ import annotations

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Event(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("مسودة")
        PUBLISHED = "published", _("منشور")
        CANCELLED = "cancelled", _("ملغى")

    title = models.CharField(_("العنوان"), max_length=200)
    title_en = models.CharField(_("العنوان (إنجليزي)"), max_length=200, blank=True)
    slug = models.SlugField(_("الرابط"), max_length=220, unique=True, allow_unicode=True, blank=True)
    description = models.TextField(_("الوصف"), blank=True)

    start_at = models.DateTimeField(_("يبدأ"), db_index=True)
    end_at = models.DateTimeField(_("ينتهي"), blank=True, null=True)
    location = models.CharField(_("المكان"), max_length=150, default=_("الملعب الرئيسي — المركز"))

    image = models.ImageField(_("الصورة"), upload_to="events/", blank=True, null=True)
    capacity = models.PositiveIntegerField(_("السعة القصوى"), default=50)
    is_free = models.BooleanField(_("مجاني"), default=True)
    price = models.DecimalField(_("السعر (جنيه)"), max_digits=8, decimal_places=2, default=0)

    min_age = models.PositiveSmallIntegerField(_("الحد الأدنى للسن"), null=True, blank=True)
    max_age = models.PositiveSmallIntegerField(_("الحد الأقصى للسن"), null=True, blank=True)
    requires_registration = models.BooleanField(_("يتطلب تسجيلًا مسبقًا"), default=True)

    status = models.CharField(_("الحالة"), max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_events", verbose_name=_("أُضيف بواسطة"))

    class Meta:
        verbose_name = _("نشاط")
        verbose_name_plural = _("الأنشطة")
        ordering = ["start_at"]
        indexes = [models.Index(fields=["status", "start_at"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            import re

            base = re.sub(r"[^\w\u0600-\u06FF-]+", "-", self.title.strip()).strip("-") or "event"
            slug, i = base, 2
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def confirmed_count(self) -> int:
        return self.registrations.filter(status=EventRegistration.Status.CONFIRMED).count()

    @property
    def active_count(self) -> int:
        """المقاعد المحجوزة فعليًا: مؤكدة + بانتظار الدفع."""
        return self.registrations.filter(
            status__in=[EventRegistration.Status.CONFIRMED, EventRegistration.Status.PENDING]
        ).count()

    @property
    def seats_left(self) -> int:
        return max(0, self.capacity - self.active_count)

    @property
    def is_full(self) -> bool:
        return self.active_count >= self.capacity

    def get_absolute_url(self) -> str:
        return reverse("events:detail", kwargs={"slug": self.slug})

    def __str__(self) -> str:
        return self.title


class EventRegistration(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("قيد الدفع")
        CONFIRMED = "confirmed", _("مؤكد")
        WAITLIST = "waitlist", _("قائمة انتظار")
        CANCELLED = "cancelled", _("ملغى")

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations", verbose_name=_("النشاط"))
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="event_registrations", verbose_name=_("العضو"))
    status = models.CharField(_("الحالة"), max_length=10, choices=Status.choices, default=Status.CONFIRMED, db_index=True)

    class Meta:
        verbose_name = _("تسجيل نشاط")
        verbose_name_plural = _("تسجيلات الأنشطة")
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="unique_registration_per_event"),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.event} ({self.get_status_display()})"
