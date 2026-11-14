"""
Memberships — أنواع الاشتراك، الكوبونات، وسجل العضوية الكامل.
التصميم: كل تجديد = صف Membership جديد (دفتر تواريخ كامل).
الحالة: نشط / منتهي / قيد المراجعة / موقوف / ملغى.
"""
from __future__ import annotations

import secrets
from datetime import date

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class MembershipType(TimeStampedModel):
    """نوع الاشتراك المتاح للبيع — سنوي، بسعر ثابت بالجنيه."""

    name_ar = models.CharField(_("الاسم (عربي)"), max_length=120)
    name_en = models.CharField(_("الاسم (إنجليزي)"), max_length=120, blank=True)
    description = models.CharField(_("الوصف"), max_length=300, blank=True)
    price = models.DecimalField(_("السعر (جنيه)"), max_digits=9, decimal_places=2)
    duration_months = models.PositiveSmallIntegerField(_("المدة بالأشهر"), default=12)
    min_age = models.PositiveSmallIntegerField(_("الحد الأدنى للسن (اختياري)"), null=True, blank=True)
    max_age = models.PositiveSmallIntegerField(_("الحد الأقصى للسن (اختياري)"), null=True, blank=True)
    is_active = models.BooleanField(_("متاح للبيع"), default=True)
    order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("نوع اشتراك")
        verbose_name_plural = _("أنواع الاشتراكات")
        ordering = ["order", "price"]

    def __str__(self) -> str:
        return f"{self.name_ar} — {self.price}ج"


class Coupon(TimeStampedModel):
    """كوبون خصم — نسبة مئوية أو قيمة ثابتة بالجنيه."""

    class Kind(models.TextChoices):
        PERCENT = "percent", _("نسبة مئوية ٪")
        FIXED = "fixed", _("قيمة ثابتة (ج)")

    code = models.CharField(_("الكود"), max_length=30, unique=True)
    kind = models.CharField(_("نوع الخصم"), max_length=10, choices=Kind.choices, default=Kind.PERCENT)
    value = models.DecimalField(_("القيمة"), max_digits=9, decimal_places=2)

    valid_from = models.DateField(_("ساري من"), default=timezone.localdate)
    valid_to = models.DateField(_("ساري حتى"))
    usage_limit = models.PositiveIntegerField(_("الحد الأقصى للاستخدام (فارغ = بلا حد)"), null=True, blank=True)
    used_count = models.PositiveIntegerField(_("عدد مرات الاستخدام"), default=0, editable=False)
    min_amount = models.DecimalField(_("الحد الأدنى للفاتورة (ج)"), max_digits=9, decimal_places=2, default=0)
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("كوبون خصم")
        verbose_name_plural = _("كوبونات الخصم")

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} ({self.get_kind_display()}: {self.value})"


def generate_reference() -> str:
    return f"REN-{timezone.now().year}-{secrets.token_hex(3).upper()}"


class Membership(TimeStampedModel):
    """اشتراك واحد — صف مستقل لكل فترة اشتراك (دفتر تواريخ)."""

    class Status(models.TextChoices):
        PENDING = "pending_review", _("قيد المراجعة")
        ACTIVE = "active", _("نشط")
        EXPIRED = "expired", _("منتهي")
        SUSPENDED = "suspended", _("موقوف")
        CANCELLED = "cancelled", _("ملغي")

    member = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="memberships", verbose_name=_("صاحب الحساب"))
    for_user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="own_memberships", null=True, blank=True, verbose_name=_("المستفيد (نفسه)"))
    for_dependent = models.ForeignKey("accounts.Dependent", on_delete=models.CASCADE, related_name="memberships", null=True, blank=True, verbose_name=_("المستفيد (تابع)"))

    membership_type = models.ForeignKey(MembershipType, on_delete=models.PROTECT, related_name="memberships", verbose_name=_("نوع الاشتراك"))
    reference = models.CharField(_("كود الطلب"), max_length=30, unique=True, default=generate_reference)

    start_date = models.DateField(_("تاريخ البداية"))
    end_date = models.DateField(_("تاريخ النهاية"))
    status = models.CharField(_("الحالة"), max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)

    base_amount = models.DecimalField(_("السعر قبل الخصم (ج)"), max_digits=9, decimal_places=2)
    discount_amount = models.DecimalField(_("الخصم (ج)"), max_digits=9, decimal_places=2, default=0)
    total_amount = models.DecimalField(_("الإجمالي (ج)"), max_digits=9, decimal_places=2)
    fine_amount = models.DecimalField(_("غرامة التأخير (ج)"), max_digits=9, decimal_places=2, default=0)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships", verbose_name=_("الكوبون المستخدم"))

    note = models.CharField(_("ملاحظات"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("اشتراك")
        verbose_name_plural = _("الاشتراكات")
        ordering = ["-end_date", "-created_at"]
        indexes = [models.Index(fields=["member", "status"]), models.Index(fields=["status", "end_date"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(start_date__lte=models.F("end_date")), name="membership_start_before_end"),
            # بالتحديد: إما for_user أو for_dependent — مش الاتنين ولا ولا
            models.CheckConstraint(condition=models.Q(for_user__isnull=False) ^ models.Q(for_dependent__isnull=False), name="membership_exactly_one_beneficiary"),
        ]

    @property
    def beneficiary_name(self) -> str:
        if self.for_dependent:
            return self.for_dependent.full_name_ar
        profile = getattr(self.for_user, "profile", None)
        return (profile.full_name_ar if profile else None) or (self.for_user.get_full_name() if self.for_user else "?")

    @property
    def days_left(self) -> int:
        return max(0, (self.end_date - timezone.now().date()).days)

    @property
    def is_current(self) -> bool:
        today = timezone.now().date()
        return self.status == self.Status.ACTIVE and self.start_date <= today <= self.end_date

    @property
    def progress_percent(self) -> int:
        total = (self.end_date - self.start_date).days or 1
        elapsed = min(total, max(0, (timezone.now().date() - self.start_date).days))
        return int(elapsed * 100 / total)

    def __str__(self) -> str:
        return f"{self.beneficiary_name} — {self.membership_type.name_ar} ({self.get_status_display()})"


class MembershipRenewal(TimeStampedModel):
    """سجل أقدمية: كل طلب تجديد يتسجل هنا حتى لو الأدمن رفضه."""

    class Initiator(models.TextChoices):
        SELF = "self", _("العضو بنفسه")
        STAFF = "staff", _("الموظف")
        SYSTEM = "system", _("النظام")

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="renewals", verbose_name=_("الاشتراك"))
    initiator = models.CharField(_("من بدأ"), max_length=10, choices=Initiator.choices, default=Initiator.SELF)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("طلب تجديد")
        verbose_name_plural = _("طلبات التجديد")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"تجديد {self.membership.reference} — {self.get_initiator_display()}"


class CouponRedemption(TimeStampedModel):
    """استهلاك كوبون مرتبط باشتراك محدد — لمنع الاستخدام المزدوج والمحاسبة."""

    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions", verbose_name=_("الكوبون"))
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="coupon_redemptions", verbose_name=_("الاشتراك"))
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="coupon_redemptions", verbose_name=_("المستخدم"))
    discount_amount = models.DecimalField(_("قيمة الخصم (ج)"), max_digits=9, decimal_places=2)

    class Meta:
        verbose_name = _("استخدام كوبون")
        verbose_name_plural = _("استخدامات الكوبونات")
        constraints = [
            models.UniqueConstraint(fields=["coupon", "membership"], name="unique_coupon_per_membership"),
        ]
