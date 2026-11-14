"""
Courses — دورات المركز: التسجيل بشروط، الحضور، التقييم، الشهادات.
نموذج الدفع موحد مع باقي التطبيق (Payment kind=course).
"""
from __future__ import annotations

import secrets

from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.payments.models import ReferenceCounter
from apps.tournaments.models import Sport


class Course(TimeStampedModel):
    class Level(models.TextChoices):
        BEGINNER = "beginner", _("مبتدئ")
        INTERMEDIATE = "intermediate", _("متوسط")
        ADVANCED = "advanced", _("متقدم")
        ALL = "all", _("كل المستويات")

    class Gender(models.TextChoices):
        MALE = "M", _("بنين")
        FEMALE = "F", _("بنات")
        MIXED = "X", _("مشترك")

    class PriceType(models.TextChoices):
        MONTHLY = "monthly", _("شهري")
        FULL = "full", _("الدورة كاملة")
        FREE = "free", _("مجاني")

    class Status(models.TextChoices):
        DRAFT = "draft", _("مسودة")
        OPEN = "open", _("التسجيل مفتوح")
        ONGOING = "ongoing", _("جارية")
        COMPLETED = "completed", _("منتهية")
        CANCELLED = "cancelled", _("ملغاة")

    name = models.CharField(_("اسم الدورة"), max_length=180)
    name_en = models.CharField(_("الاسم (إنجليزي)"), max_length=180, blank=True)
    slug = models.SlugField(_("الرابط"), max_length=220, unique=True, blank=True, allow_unicode=True)
    sport = models.ForeignKey(Sport, on_delete=models.PROTECT, related_name="courses", verbose_name=_("الرياضة"))
    description = models.TextField(_("الوصف وأهداف الدورة"), blank=True)

    level = models.CharField(_("المستوى"), max_length=15, choices=Level.choices, default=Level.ALL)
    gender = models.CharField(_("الفئة"), max_length=1, choices=Gender.choices, default=Gender.MIXED)
    age_min = models.PositiveSmallIntegerField(_("من سن"), default=4)
    age_max = models.PositiveSmallIntegerField(_("حتى سن"), default=99)

    schedule = models.CharField(_("الأيام والمواعيد الأسبوعية"), max_length=180, default=_("السبت — ٥:٠٠ مساءً"))
    location = models.CharField(_("المكان"), max_length=150, default=_("صالة المركز"))
    start_date = models.DateField(_("تاريخ البداية"), null=True, blank=True)
    duration_weeks = models.PositiveSmallIntegerField(_("المدة بالأسابيع"), default=8)

    price = models.DecimalField(_("السعر (ج)"), max_digits=9, decimal_places=2, default=0)
    price_type = models.CharField(_("طريقة السعر"), max_length=10, choices=PriceType.choices, default=PriceType.MONTHLY)
    capacity = models.PositiveIntegerField(_("السعة القصوى (للدورة)"), default=20)
    requires_medical = models.BooleanField(_("يتطلب فحصًا طبيًا/إقرارًا صحيًا"), default=False)

    status = models.CharField(_("الحالة"), max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    cover = models.ImageField(_("الغلاف"), upload_to="courses/", blank=True, null=True)
    coach = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="coached_courses", verbose_name=_("المدرب"))


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
        verbose_name = _("دورة")
        verbose_name_plural = _("الدورات")
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            import re

            base = re.sub(r"[^\w\u0600-\u06FF-]+", "-", self.name.strip()).strip("-") or "course"
            slug, i = base, 2
            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def confirmed_count(self) -> int:
        return self.enrollments.filter(status=CourseEnrollment.Status.CONFIRMED).count()

    @property
    def seats_left(self) -> int:
        return max(0, self.capacity - self.confirmed_count)

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN and self.seats_left > 0

    def get_absolute_url(self) -> str:
        return reverse("courses:detail", kwargs={"slug": self.slug})

    def __str__(self) -> str:
        return self.name


class CourseGroup(TimeStampedModel):
    """مجموعة/دفعة داخل الدورة (مثلاً: مجموعة السبت ٥م)."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="groups", verbose_name=_("الدورة"))
    name = models.CharField(_("اسم المجموعة"), max_length=80)
    schedule = models.CharField(_("الأيام والمواعيد"), max_length=120, blank=True)
    capacity = models.PositiveIntegerField(_("السعة"), default=15)
    coach = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="coached_groups", verbose_name=_("المدرب"))

    class Meta:
        verbose_name = _("مجموعة")
        verbose_name_plural = _("المجموعات")
        ordering = ["name"]

    @property
    def confirmed_count(self) -> int:
        return self.enrollments.filter(status=CourseEnrollment.Status.CONFIRMED).count()

    def __str__(self) -> str:
        return f"{self.course.name} — {self.name}"


class CourseEnrollment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("قيد المراجعة")
        CONFIRMED = "confirmed", _("مؤكد")
        WAITLIST = "waitlist", _("قائمة انتظار")
        CANCELLED = "cancelled", _("ملغى")
        COMPLETED = "completed", _("مكتمل")

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments", verbose_name=_("الدورة"))
    group = models.ForeignKey(CourseGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="enrollments", verbose_name=_("المجموعة"))
    member = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="course_enrollments", verbose_name=_("العضو صاحب الحساب"))

    for_user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, null=True, blank=True, related_name="own_course_enrollments", verbose_name=_("المستفيد (نفسه)"))
    for_dependent = models.ForeignKey("accounts.Dependent", on_delete=models.CASCADE, null=True, blank=True, related_name="course_enrollments", verbose_name=_("المستفيد (تابع)"))

    status = models.CharField(_("الحالة"), max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    reference = models.CharField(_("كود التسجيل"), max_length=30, unique=True, blank=True)
    fee_amount = models.DecimalField(_("الرسوم (ج)"), max_digits=9, decimal_places=2, default=0)
    health_acknowledged = models.BooleanField(_("أقر بصحة البيانات الصحية"), default=False)
    coach_note = models.CharField(_("ملاحظة المدرب"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("تسجيل دورة")
        verbose_name_plural = _("تسجيلات الدورات")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(for_user__isnull=False) ^ models.Q(for_dependent__isnull=False),
                name="enrollment_exactly_one_beneficiary",
            ),
            models.UniqueConstraint(fields=["course", "for_user", "for_dependent"], name="unique_enrollment_per_course_beneficiary"),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"CRS-{timezone.now().year}-{secrets.token_hex(3).upper()}"
        super().save(*args, **kwargs)

    @property
    def beneficiary_name(self) -> str:
        if self.for_dependent:
            return self.for_dependent.full_name_ar
        profile = getattr(self.for_user, "profile", None)
        return (profile.full_name_ar if profile else None) or (self.for_user.get_full_name() if self.for_user else "؟")

    @property
    def beneficiary_age(self):
        person = self.for_dependent or getattr(self.for_user, "profile", None)
        return getattr(person, "age", None)

    @property
    def attendance_percent(self):
        total = self.attendance.count()
        if total == 0:
            return 0
        return round(self.attendance.filter(present=True).count() * 100 / total)

    def __str__(self) -> str:
        return f"{self.beneficiary_name} — {self.course.name}"


class Attendance(TimeStampedModel):
    """حضور جلسة — يُسجله المدرب من الموبايل."""

    enrollment = models.ForeignKey(CourseEnrollment, on_delete=models.CASCADE, related_name="attendance", verbose_name=_("التسجيل"))
    session_date = models.DateField(_("تاريخ الجلسة"), db_index=True)
    present = models.BooleanField(_("حاضر"), default=True)
    marked_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="marked_attendances", verbose_name=_("سُجل بواسطة"))

    class Meta:
        verbose_name = _("حضور")
        verbose_name_plural = _("الحضور")
        ordering = ["-session_date"]
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "session_date"], name="unique_attendance_per_session"),
        ]


class CourseEvaluation(TimeStampedModel):
    enrollment = models.OneToOneField(CourseEnrollment, on_delete=models.CASCADE, related_name="evaluation", verbose_name=_("التسجيل"))
    coach = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="coach_evaluations", verbose_name=_("المدرب"))
    rating = models.PositiveSmallIntegerField(_("التقييم (1-5)"), default=5)
    note = models.CharField(_("ملاحظات"), max_length=500, blank=True)

    class Meta:
        verbose_name = _("تقييم دورة")
        verbose_name_plural = _("تقييمات الدورات")


class Certificate(models.Model):
    """شهادة إتمام — تُصدر تلقائيًا عند اكتمال الدورة."""

    enrollment = models.OneToOneField(CourseEnrollment, on_delete=models.CASCADE, related_name="certificate", verbose_name=_("التسجيل"))
    number = models.CharField(_("رقم الشهادة"), max_length=30, unique=True, blank=True)
    issued_at = models.DateTimeField(_("صدرت في"), auto_now_add=True)

    class Meta:
        verbose_name = _("شهادة")
        verbose_name_plural = _("الشهادات")

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = ReferenceCounter.next_number("CERT")
        super().save(*args, **kwargs)

    @property
    def recipient_name(self) -> str:
        return self.enrollment.beneficiary_name

    def __str__(self) -> str:
        return self.number
