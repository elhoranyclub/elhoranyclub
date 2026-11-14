"""
Trips — رحلات المركز: حجز مقاعد، موافقة ولي الأمر للقاصرين، قوائم ركاب وحضور.
المقاعد تُحجز ذريًا (select_for_update) — الدفع يفعّل الحجز للركاب الأعضاء.
"""
from __future__ import annotations

import secrets

from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.payments.models import ReferenceCounter


class Trip(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("مسودة")
        OPEN = "open", _("الحجز مفتوح")
        FULL = "full", _("مكتملة العدد")
        COMPLETED = "completed", _("منجزة")
        CANCELLED = "cancelled", _("ملغاة")

    name = models.CharField(_("اسم الرحلة"), max_length=180)
    name_en = models.CharField(_("الاسم (إنجليزي)"), max_length=180, blank=True)
    slug = models.SlugField(_("الرابط"), max_length=220, unique=True, blank=True, allow_unicode=True)
    destination = models.CharField(_("الوجهة"), max_length=120)
    description = models.TextField(_("الوصف وبرنامج الرحلة"), blank=True)

    trip_date = models.DateField(_("تاريخ الرحلة"), db_index=True)
    return_date = models.DateField(_("تاريخ العودة (لو أيام)"), null=True, blank=True)
    meeting_point = models.CharField(_("نقطة التجمع"), max_length=150, default=_("بوابة المركز"))
    meeting_time = models.TimeField(_("ساعة التجمع"), default="08:00")

    member_price = models.DecimalField(_("سعر العضو (ج)"), max_digits=9, decimal_places=2, default=0)
    guest_price = models.DecimalField(_("سعر المرافق غير العضو (ج)"), max_digits=9, decimal_places=2, default=0)
    capacity = models.PositiveIntegerField(_("عدد المقاعد"), default=40)
    min_age = models.PositiveSmallIntegerField(_("الحد الأدنى للسن (اختياري)"), null=True, blank=True)
    max_age = models.PositiveSmallIntegerField(_("الحد الأقصى للسن (اختياري)"), null=True, blank=True)

    rules = models.TextField(_("القواعد والبنود"), blank=True)
    supervisors = models.CharField(_("المشرفون"), max_length=255, blank=True)
    cover = models.ImageField(_("الغلاف"), upload_to="trips/", blank=True, null=True)
    status = models.CharField(_("الحالة"), max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)


    # ===== لينك خارجي (اختياري) =====
    # زي: برنامج/training على موقع وزارة الشباب والرياضة أو أي موقع تاني.
    # لو فاضي — مش بيظهر زرار في الواجهة.
    external_url = models.URLField(
        _("لينك خارجي"),
        max_length=500,
        blank=True,
        default="",
        help_text=_("اختياري — لينك صفحة خارجية (برنامج، كراسةموقع وزارة الشباب). اتركه فاضي لو مفيش."),
    )
    external_label = models.CharField(
        _("نص زرار اللينك"),
        max_length=80,
        blank=True,
        default="",
        help_text=_("اختياري — النص اللي هيظهر على الزرار (مثال: «رابط البرنامج على موقع الوزارة»)."),
    )

    class Meta:
        verbose_name = _("رحلة")
        verbose_name_plural = _("الرحلات")
        ordering = ["trip_date"]

    def save(self, *args, **kwargs):
        if not self.slug:
            import re

            base = re.sub(r"[^\w\u0600-\u06FF-]+", "-", self.name.strip()).strip("-") or "trip"
            slug, i = base, 2
            while Trip.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def seats_taken(self) -> int:
        return self.bookings.filter(status__in=[TripBooking.Status.CONFIRMED, TripBooking.Status.PENDING]).aggregate(total=models.Sum("passengers_count"))["total"] or 0

    @property
    def seats_left(self) -> int:
        return max(0, self.capacity - self.seats_taken)

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN and self.seats_left > 0

    def get_absolute_url(self) -> str:
        return reverse("trips:detail", kwargs={"slug": self.slug})

    def __str__(self) -> str:
        return f"{self.name} ({self.trip_date})"


class TripBooking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("قيد الدفع/المراجعة")
        CONFIRMED = "confirmed", _("مؤكد")
        WAITLIST = "waitlist", _("قائمة انتظار")
        CANCELLED = "cancelled", _("ملغى")

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="bookings", verbose_name=_("الرحلة"))
    booked_by = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="trip_bookings", verbose_name=_("الحاجز"))
    reference = models.CharField(_("كود الحجز"), max_length=30, unique=True, blank=True)

    passengers_count = models.PositiveSmallIntegerField(_("عدد الركاب"), default=1)
    member_count = models.PositiveSmallIntegerField(_("عدد الركاب الأعضاء"), default=0)
    guest_count = models.PositiveSmallIntegerField(_("عدد المرافقين"), default=0)
    total_amount = models.DecimalField(_("الإجمالي (ج)"), max_digits=9, decimal_places=2, default=0)

    status = models.CharField(_("الحالة"), max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    note = models.CharField(_("ملاحظة للحافلة"), max_length=500, blank=True)

    class Meta:
        verbose_name = _("حجز رحلة")
        verbose_name_plural = _("حجوزات الرحلات")
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = ReferenceCounter.next_number("TRIP") if hasattr(ReferenceCounter, "next_number") else f"TRP-{timezone.now().year}-{secrets.token_hex(3).upper()}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.reference} — {self.trip.name}"


class TripPassenger(TimeStampedModel):
    class Relation(models.TextChoices):
        SELF = "self", _("الحاجز نفسه")
        DEPENDENT = "dependent", _("تابع")
        GUEST = "guest", _("مرافق")

    booking = models.ForeignKey(TripBooking, on_delete=models.CASCADE, related_name="passengers", verbose_name=_("الحجز"))
    relation = models.CharField(_("صلة الركاب"), max_length=10, choices=Relation.choices)
    full_name = models.CharField(_("الاسم كاملًا"), max_length=150)
    age = models.PositiveSmallIntegerField(_("السن"), null=True, blank=True)
    medical_notes = models.CharField(_("ملاحظات صحية"), max_length=255, blank=True)
    present = models.BooleanField(_("حاضر يوم الرحلة"), default=False)

    class Meta:
        verbose_name = _("راكب")
        verbose_name_plural = _("الركاب")

    def __str__(self) -> str:
        return self.full_name


class GuardianConsent(TimeStampedModel):
    """إقرار وموافقة ولي الأمر إلكترونيًا للقاصرين — يُحتفظ به قانونيًا."""

    passenger = models.OneToOneField(TripPassenger, on_delete=models.CASCADE, related_name="consent", verbose_name=_("الراكب"))
    booking = models.ForeignKey(TripBooking, on_delete=models.CASCADE, related_name="consents", verbose_name=_("الحجز"))
    guardian = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="signed_consents", verbose_name=_("ولي الأمر"))
    signature_name = models.CharField(_("الاسم كما جرى التوقيع"), max_length=150)
    consent_text = models.TextField(_("نص الإقرار"))
    agreed_at = models.DateTimeField(_("تاريخ الموافقة"), default=timezone.now)
    ip_address = models.GenericIPAddressField(_("IP"), null=True, blank=True)

    class Meta:
        verbose_name = _("موافقة ولي أمر")
        verbose_name_plural = _("موافقات أولياء الأمور")

    CONSENT_TEXT = (
        "أقرّ أنا ولي الأمر بأنني اطلعت على برنامج الرحلة وقواعدها (مواعيد التجمع والتحرك، شروط اللعب، تعليمات الأمان "
        "ومواعيد العودة)، وأن اللاعب تحت رعايتي يتمتع بصحة جيدة تسمح له بالمشاركة، وأنني أوافق على اشتراكه في الرحلة "
        "وعلى التزام المشرفين بالقرارات الطبية والإدارية للرحلة. وأقرّ أيضًا بأن اللاعب سيستمع لتعليمات المشرفين."
    )

    def __str__(self) -> str:
        return f"موافقة {self.guardian} — {self.passenger.full_name}"
