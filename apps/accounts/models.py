"""
Accounts — مركز شباب الحوراني
Custom User (login by Egyptian mobile), Profile, Guardian/Dependent,
membership numbering (YC-YYYY-000123) and OTP verification records.
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

PHONE_HELP = _("رقم مصري بصيغة 01xxxxxxxxx")


class User(AbstractUser):
    """Egyptian mobile-first user. Login uses phone, not username."""

    phone = models.CharField(_("رقم الموبايل"), max_length=15, unique=True, null=True, blank=True, help_text=PHONE_HELP)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = _("مستخدم")
        verbose_name_plural = _("المستخدمين")

    def __str__(self) -> str:
        return self.get_full_name() or self.phone or self.username


class MembershipCounter(models.Model):
    """Per-year sequence for membership numbers — Postgres-safe (row lock)."""

    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.year}: {self.last_number}"

    @classmethod
    def next_number(cls) -> int:
        year = timezone.now().year
        with transaction.atomic():
            counter, _created = cls.objects.select_for_update().get_or_create(year=year)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return counter.last_number


class MembershipNumberCounter(models.Model):
    """Singleton (pk=1): next plain sequential membership number.

    Numbers continue after the largest numeric number in the ledger (imported from the paper
    registry), so self-registered members get 1524 after 1523, etc.
    """

    last_number = models.PositiveBigIntegerField(default=0)

    def __str__(self) -> str:
        return str(self.last_number)


def _max_numeric_membership_number() -> int:
    """Largest integer-parsable membership_number across profiles, dependents and the ledger."""
    best = 0
    for model in (Profile, Dependent, MemberRegistry):
        for (num,) in model.objects.filter(membership_number__regex=r"^\d+$").values_list("membership_number", flat=False):
            try:
                value = int(num or 0)
            except (TypeError, ValueError):
                continue
            if value > best:
                best = value
    return best


def allocate_membership_number() -> str:
    """Next plain sequential number — race-safe, synced with the ledger maximum."""
    with transaction.atomic():
        counter, _created = MembershipNumberCounter.objects.select_for_update().get_or_create(pk=1)
        counter.last_number = max(counter.last_number, _max_numeric_membership_number())
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        return str(counter.last_number)


class MemberRegistry(TimeStampedModel):
    """Rows imported from the paper ledger — the pre-existing registry of club members.

    These are NOT accounts: members self-register on the site, then staff links their profile
    to a registry row (copying membership number, national ID and general-assembly status).
    """

    full_name_ar = models.CharField(_("الاسم (عربي)"), max_length=120)
    national_id = models.CharField(_("الرقم القومي"), max_length=14, blank=True, db_index=True,
                                   help_text=_("14 رقمًا — تُستخدم عند ربط الدفتر بحساب العضو بعد التسجيل"))
    membership_number = models.CharField(_("رقم العضوية"), max_length=20, unique=True, db_index=True)

    is_general_assembly = models.BooleanField(_("عضو اللجنة العمومية"), default=False)
    assembly_position = models.CharField(_("المنصب في اللجنة العمومية"), max_length=120, blank=True)

    paid_until = models.DateField(_("مدفوع حتى"), null=True, blank=True)
    last_payment_amount = models.DecimalField(_("آخر مبلغ مدفوع (ج)"), max_digits=9, decimal_places=2, null=True, blank=True)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    linked_profile = models.OneToOneField(
        "accounts.Profile", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="registry_entry", verbose_name=_("البروفايل المرتبط"),
    )

    class Meta:
        verbose_name = _("سجل الدفتر")
        verbose_name_plural = _("سجل الأعضاء (الدفتر)")
        ordering = ["membership_number"]

    def __str__(self) -> str:
        return f"{self.membership_number} — {self.full_name_ar}"


def generate_membership_number() -> str:
    """Plain sequential number continuing after the ledger (1523 → 1524)."""
    return allocate_membership_number()


class Profile(TimeStampedModel):
    """عضوية + بيانات شخصية. الربط OneToOne مع User."""

    class Gender(models.TextChoices):
        MALE = "M", _("ذكر")
        FEMALE = "F", _("أنثى")

    class ShirtSize(models.TextChoices):
        XS = "XS", "XS"
        S = "S", "S"
        M = "M", "M"
        L = "L", "L"
        XL = "XL", "XL"
        XXL = "XXL", "XXL"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    membership_number = models.CharField(_("رقم العضوية"), max_length=20, unique=True, editable=False)

    full_name_ar = models.CharField(_("الاسم بالعربي"), max_length=120)
    full_name_en = models.CharField(_("الاسم بالإنجليزي"), max_length=120, blank=True)
    birth_date = models.DateField(_("تاريخ الميلاد"), null=True, blank=True)
    gender = models.CharField(_("النوع"), max_length=1, choices=Gender.choices, blank=True)

    # اختياري — يُعرض آخر 4 أرقام فقط في الواجهة
    national_id = models.CharField(_("الرقم القومي"), max_length=14, blank=True)

    # اللجنة العمومية — يحددهما الموظف المسؤول من شاشة الإدارة بعد التسجيل
    is_general_assembly = models.BooleanField(_("عضو اللجنة العمومية"), default=False)
    assembly_position = models.CharField(_("المنصب في اللجنة العمومية"), max_length=120, blank=True)

    address = models.CharField(_("العنوان"), max_length=255, blank=True)
    governorate = models.CharField(_("المحافظة"), max_length=60, default="القاهرة")
    photo = models.ImageField(_("الصورة الشخصية"), upload_to="members/", blank=True, null=True)

    emergency_contact_name = models.CharField(_("جهة اتصال الطوارئ (الاسم)"), max_length=120, blank=True)
    emergency_contact_phone = models.CharField(_("جهة اتصال الطوارئ (الموبايل)"), max_length=15, blank=True)

    health_notes = models.TextField(_("الحالة الصحية / الحساسية"), max_length=1000, blank=True)
    shirt_size = models.CharField(_("مقاس الزي الرياضي"), max_length=4, choices=ShirtSize.choices, blank=True)

    joined_at = models.DateField(_("تاريخ الانضمام"), auto_now_add=True)

    # أول مرة يسجّل دخوله — يشوف صفحة «اعرف الموقع أكتر» (فيديو التدريب)
    guide_seen = models.BooleanField(_("شاف دليل الاستخدام"), default=False)
    # آخر دور شاف دليله — لو صلاحيته اتغيّرت، الفيديو الجديد يظهر تاني
    guide_seen_role = models.CharField(_("الدور اللي شاف دليله"), max_length=20, blank=True, default="")

    class Meta:
        verbose_name = _("الملف الشخصي")
        verbose_name_plural = _("الملفات الشخصية")

    def save(self, *args, **kwargs):
        if not self.membership_number:
            self.membership_number = generate_membership_number()
        super().save(*args, **kwargs)

    @property
    def national_id_masked(self) -> str:
        if len(self.national_id) >= 4:
            return "•" * (len(self.national_id) - 4) + self.national_id[-4:]
        return "—" if not self.national_id else "•" * len(self.national_id)

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = timezone.now().date()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    def __str__(self) -> str:
        return f"{self.full_name_ar} ({self.membership_number})"


class Dependent(TimeStampedModel):
    """ابن/ابنة لولي الأمر — عضو مستقل برقم عضوية خاص."""

    class Relation(models.TextChoices):
        SON = "son", _("ابن")
        DAUGHTER = "daughter", _("ابنة")

    guardian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dependents", verbose_name=_("ولي الأمر"))
    membership_number = models.CharField(_("رقم العضوية"), max_length=20, unique=True, editable=False)

    full_name_ar = models.CharField(_("الاسم بالعربي"), max_length=120)
    full_name_en = models.CharField(_("الاسم بالإنجليزي"), max_length=120, blank=True)
    birth_date = models.DateField(_("تاريخ الميلاد"))
    gender = models.CharField(_("النوع"), max_length=1, choices=Profile.Gender.choices)
    relation = models.CharField(_("صلة القرابة"), max_length=10, choices=Relation.choices, default=Relation.SON)
    national_id = models.CharField(_("الرقم القومي"), max_length=14, blank=True)
    photo = models.ImageField(_("الصورة"), upload_to="members/dependents/", blank=True, null=True)
    health_notes = models.TextField(_("الحالة الصحية / الحساسية"), max_length=1000, blank=True)

    class Meta:
        verbose_name = _("تابع")
        verbose_name_plural = _("التابعين")
        constraints = [
            models.UniqueConstraint(fields=["guardian", "full_name_ar", "birth_date"], name="unique_dependent_per_guardian"),
        ]

    def save(self, *args, **kwargs):
        if not self.membership_number:
            self.membership_number = generate_membership_number()
        super().save(*args, **kwargs)

    @property
    def national_id_masked(self) -> str:
        if len(self.national_id) >= 4:
            return "•" * (len(self.national_id) - 4) + self.national_id[-4:]
        return "—"

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = timezone.now().date()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    def __str__(self) -> str:
        return f"{self.full_name_ar} — {self.get_relation_display()} ({self.membership_number})"


class OTP(models.Model):
    """رمز تحقق لمرة واحدة — يُشفّر (hash) ولا يُخزّن نصًا صريحًا."""

    class Purpose(models.TextChoices):
        REGISTER = "register", _("تسجيل حساب جديد")
        RESET_PASSWORD = "reset", _("نسيت كلمة السر")

    phone = models.CharField(_("رقم الموبايل"), max_length=15, db_index=True)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(_("الغرض"), max_length=20, choices=Purpose.choices)
    created_at = models.DateTimeField(_("أُنشئ في"), auto_now_add=True)
    expires_at = models.DateTimeField(_("ينتهي في"))
    attempts = models.PositiveSmallIntegerField(_("محاولات"), default=0)
    consumed = models.BooleanField(_("مُستهلَك"), default=False)

    MAX_ATTEMPTS = 5
    TTL_MINUTES = 10

    class Meta:
        verbose_name = _("رمز تحقق")
        verbose_name_plural = _("رموز التحقق")
        indexes = [models.Index(fields=["phone", "purpose", "-created_at"])]

    @classmethod
    def issue(cls, phone: str, purpose: str) -> tuple["OTP", str]:
        code = f"{secrets.randbelow(1_000_000):06d}"
        otp = cls.objects.create(
            phone=phone,
            code_hash=make_password(code),
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=cls.TTL_MINUTES),
        )
        return otp, code

    def verify(self, code: str) -> tuple[bool, str]:
        if self.consumed:
            return False, _("هذا الرمز تم استخدامه بالفعل.")
        if timezone.now() > self.expires_at:
            return False, _("انتهت صلاحية الرمز، اطلب رمزًا جديدًا.")
        if self.attempts >= self.MAX_ATTEMPTS:
            return False, _("وصلت للحد الأقصى من المحاولات، اطلب رمزًا جديدًا.")
        self.attempts += 1
        self.save(update_fields=["attempts"])
        if not check_password(code, self.code_hash):
            return False, _("الرمز غير صحيح.")
        self.consumed = True
        self.save(update_fields=["consumed"])
        return True, ""

    def __str__(self) -> str:
        return f"{self.phone} — {self.get_purpose_display()}"
