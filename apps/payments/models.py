"""
Payments — مركز شباب الحوراني
ملاحظة التصميم: ممنوع تخزين أي بيانات كوبون/بطاقة إطلاقًا. بوابة الدفع abstraction
في apps/payments/gateways (mock الآن → Paymob لاحقًا) دون تغيير أي كود يربط.
"""
from __future__ import annotations

import secrets

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class ReferenceCounter(models.Model):
    """عداد مشترك سنوي للأرقام المتسلسلة (INV/PAY) — آمن مع Postgres (row lock)."""

    class Kind(models.TextChoices):
        PAYMENT = "PAY", "PAY"
        INVOICE = "INV", "INV"
        CERTIFICATE = "CERT", "CERT"
        TRIP = "TRIP", "TRIP"

    kind = models.CharField(max_length=4, choices=Kind.choices)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kind", "year"], name="uniq_counter_kind_year")]

    @classmethod
    def next_number(cls, kind: str) -> str:
        year = timezone.now().year
        with transaction.atomic():
            counter, _created = cls.objects.select_for_update().get_or_create(kind=kind, year=year)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"{kind}-{year}-{counter.last_number:06d}"


class Payment(TimeStampedModel):
    """عملية دفع واحدة — تُربط بالاشتراك أو الحدث حسب kind."""

    class Kind(models.TextChoices):
        MEMBERSHIP = "membership", _("اشتراك سنوي")
        EVENT = "event", _("نشاط / فعالية")
        COURSE = "course", _("دورة تدريبية")
        TOURNAMENT = "tournament", _("بطولة")
        TRIP = "trip", _("رحلة")
        OTHER = "other", _("أخرى")

    class Method(models.TextChoices):
        ONLINE = "online", _("أونلاين (Paymob — mock)")
        WALLET = "wallet", _("محفظة إلكترونية")
        INSTAPAY = "instapay", _("InstaPay")
        CASH = "cash", _("نقدي بالمركز")
        OTHER = "other", _("أخرى")

    class Status(models.TextChoices):
        PENDING = "pending", _("قيد المراجعة / الدفع")
        PAID = "paid", _("مدفوع")
        FAILED = "failed", _("فشل الدفع")
        REFUNDED = "refunded", _("مسترد بالكامل")
        PARTIALLY_REFUNDED = "partially_refunded", _("مسترد جزئيًا")

    member = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="payments", verbose_name=_("العضو"))
    membership = models.ForeignKey("memberships.Membership", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments", verbose_name=_("الاشتراك المرتبط"))
    tournament_registration = models.ForeignKey("tournaments.TournamentRegistration", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments", verbose_name=_("تسجيل البطولة المرتبط"))
    course_enrollment = models.ForeignKey("courses.CourseEnrollment", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments", verbose_name=_("تسجيل الدورة المرتبط"))
    trip_booking = models.ForeignKey("trips.TripBooking", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments", verbose_name=_("حجز الرحلة المرتبط"))
    event_registration = models.ForeignKey("events.EventRegistration", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments", verbose_name=_("تسجيل الفعالية المرتبط"))
    kind = models.CharField(_("نوع الدفع"), max_length=12, choices=Kind.choices, default=Kind.MEMBERSHIP, db_index=True)
    method = models.CharField(_("طريقة الدفع"), max_length=10, choices=Method.choices, db_index=True)
    status = models.CharField(_("الحالة"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    amount = models.DecimalField(_("المبلغ (ج)"), max_digits=9, decimal_places=2)
    reference = models.CharField(_("كود الطلب"), max_length=30, unique=True, blank=True)
    provider = models.CharField(_("مزود الدفع"), max_length=30, blank=True)
    provider_ref = models.CharField(_("مرجع المزود"), max_length=100, blank=True, null=True, unique=True)
    provider_payload = models.JSONField(_("بيانات المزود (للتدقيق — بلا بطاقات)"), default=dict, blank=True)

    paid_at = models.DateTimeField(_("تاريخ الدفع"), null=True, blank=True)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("عملية دفع")
        verbose_name_plural = _("عمليات الدفع")
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = ReferenceCounter.next_number("PAY")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.reference} — {self.amount}ج ({self.get_status_display()})"


class PaymentProof(TimeStampedModel):
    """إيصال محفظة/InstaPay مرفوع من العضو — يراجعه موظف المركز."""

    class Status(models.TextChoices):
        PENDING = "pending_review", _("قيد المراجعة")
        CONFIRMED = "confirmed", _("مؤكد")
        REJECTED = "rejected", _("مرفوض")

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="proofs", verbose_name=_("العملية"))
    image = models.ImageField(_("صورة الإيصال"), upload_to="receipts/proofs/")
    amount_claimed = models.DecimalField(_("المبلغ المحول (ج)"), max_digits=9, decimal_places=2)
    operation_number = models.CharField(_("رقم العملية / مرجع التحويل"), max_length=60, blank=True)

    status = models.CharField(_("حالة المراجعة"), max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_proofs", verbose_name=_("المراجع"))
    reviewed_at = models.DateTimeField(_("تاريخ المراجعة"), null=True, blank=True)
    reviewer_note = models.CharField(_("ملاحظة المراجع"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("إيصال دفع")
        verbose_name_plural = _("إيصالات الدفع")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"إيصال {self.payment.reference} — {self.get_status_display()}"


class Invoice(models.Model):
    """فاتورة/إيصال رسمي برقم تسلسلي — تُنشأ تلقائيًا مع كل دفعة مؤكدة."""

    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="invoice", verbose_name=_("العملية"))
    number = models.CharField(_("رقم الفاتورة"), max_length=30, unique=True, blank=True)
    issued_at = models.DateTimeField(_("صدرت في"), auto_now_add=True)

    class Meta:
        verbose_name = _("فاتورة")
        verbose_name_plural = _("الفواتير")
        ordering = ["-issued_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = ReferenceCounter.next_number("INV")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.number


class Refund(TimeStampedModel):
    """استرداد كامل أو جزئي — يُسجل في الدفاتر ولا يُمحى."""

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds", verbose_name=_("العملية"))
    amount = models.DecimalField(_("المبلغ المسترد (ج)"), max_digits=9, decimal_places=2)
    reason = models.CharField(_("السبب"), max_length=255)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="refunds", verbose_name=_("بواسطة"))

    class Meta:
        verbose_name = _("استرداد")
        verbose_name_plural = _("الاستردادات")

    def __str__(self) -> str:
        return f"استرداد {self.amount}ج — {self.payment.reference}"
