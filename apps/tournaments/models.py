"""
Tournaments — بطولات المركز: التسجيل (فردي/فريق)، المباريات، الترتيب، الهدافين.
الأنظمة: دوري (Round Robin تلقائي) · مجموعات + خروج مغلوب · خروج مغلوب يدوي.
"""
from __future__ import annotations

import itertools
import math
import secrets

from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


# ============================================================ الرياضات
class Sport(models.Model):
    name_ar = models.CharField(_("الاسم (عربي)"), max_length=80, unique=True)
    name_en = models.CharField(_("الاسم (إنجليزي)"), max_length=80, blank=True)
    icon = models.CharField(_("مفتاح الأيقونة"), max_length=30, default="trophy")
    is_team_sport = models.BooleanField(_("رياضة جماعية"), default=True)
    order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("رياضة")
        verbose_name_plural = _("الرياضات")
        ordering = ["order", "name_ar"]

    def __str__(self) -> str:
        return self.name_ar


# ============================================================ البطولات
class Tournament(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("مسودة")
        REGISTRATION = "registration", _("التسجيل مفتوح")
        ONGOING = "ongoing", _("جارية")
        FINISHED = "finished", _("منتهية")
        CANCELLED = "cancelled", _("ملغاة")

    class RegistrationType(models.TextChoices):
        INDIVIDUAL = "individual", _("فردي")
        TEAM = "team", _("فريق")

    class Format(models.TextChoices):
        LEAGUE = "league", _("دوري (Round Robin)")
        GROUPS_KNOCKOUT = "groups_knockout", _("مجموعات + خروج مغلوب")
        KNOCKOUT = "knockout", _("خروج مغلوب")

    name = models.CharField(_("اسم البطولة"), max_length=180)
    name_en = models.CharField(_("الاسم (إنجليزي)"), max_length=180, blank=True)
    sport = models.ForeignKey(Sport, on_delete=models.PROTECT, related_name="tournaments", verbose_name=_("الرياضة"))
    slug = models.SlugField(_("الرابط"), max_length=220, unique=True, blank=True, allow_unicode=True)

    description = models.TextField(_("الوصف واللائحة"), blank=True)
    rules_pdf = models.FileField(_("لائحة البطولة (PDF)"), upload_to="documents/rules/", blank=True, null=True)
    sponsors = models.CharField(_("الرعاة"), max_length=300, blank=True)
    prizes = models.CharField(_("الجوائز"), max_length=300, blank=True)

    registration_start = models.DateField(_("التسجيل من"), null=True, blank=True)
    registration_end = models.DateField(_("التسجيل حتى"), null=True, blank=True)
    start_date = models.DateField(_("بداية البطولة"), null=True, blank=True)
    end_date = models.DateField(_("نهاية البطولة"), null=True, blank=True)

    registration_type = models.CharField(_("نوع التسجيل"), max_length=12, choices=RegistrationType.choices, default=RegistrationType.TEAM)
    format = models.CharField(_("نظام البطولة"), max_length=18, choices=Format.choices, default=Format.LEAGUE)
    max_teams = models.PositiveSmallIntegerField(_("الحد الأقصى للفرق/اللاعبين"), default=16)
    squad_size = models.PositiveSmallIntegerField(_("عدد اللاعبين في القائمة"), default=12)

    entry_fee = models.DecimalField(_("رسوم التسجيل (ج)"), max_digits=9, decimal_places=2, default=0)
    status = models.CharField(_("الحالة"), max_length=15, choices=Status.choices, default=Status.DRAFT, db_index=True)
    cover = models.ImageField(_("الغلاف"), upload_to="events/tournaments/", blank=True, null=True)


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
        verbose_name = _("بطولة")
        verbose_name_plural = _("البطولات")
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            import re

            base = re.sub(r"[^\w\u0600-\u06FF-]+", "-", self.name.strip()).strip("-") or "tournament"
            slug, i = base, 2
            while Tournament.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_registration_open(self) -> bool:
        today = timezone.now().date()
        if self.status != self.Status.REGISTRATION:
            return False
        if self.registration_start and today < self.registration_start:
            return False
        if self.registration_end and today > self.registration_end:
            return False
        return True

    @property
    def confirmed_count(self) -> int:
        return self.registrations.filter(status=TournamentRegistration.Status.ACCEPTED).count()

    @property
    def seats_left(self) -> int:
        return max(0, self.max_teams - self.confirmed_count)

    def get_absolute_url(self) -> str:
        return reverse("tournaments:detail", kwargs={"slug": self.slug})

    def __str__(self) -> str:
        return self.name


class TournamentCategory(TimeStampedModel):
    """فئة البطولة حسب السن والنوع — كل فئة لها سعيها وجائزتها."""

    class Gender(models.TextChoices):
        MALE = "M", _("بنين")
        FEMALE = "F", _("بنات")
        MIXED = "X", _("مشترك")

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="categories", verbose_name=_("البطولة"))
    name_ar = models.CharField(_("الفئة (عربي)"), max_length=80)
    name_en = models.CharField(_("الفئة (إنجليزي)"), max_length=80, blank=True)
    gender = models.CharField(_("النوع"), max_length=1, choices=Gender.choices, default=Gender.MALE)
    age_min = models.PositiveSmallIntegerField(_("من سن"), default=0)
    age_max = models.PositiveSmallIntegerField(_("حتى سن"), default=99)
    entry_fee = models.DecimalField(_("الرسوم (ج) — اتركه فارغًا لاستخدام رسوم البطولة"), max_digits=9, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = _("فئة بطولة")
        verbose_name_plural = _("فئات البطولة")
        ordering = ["age_min", "name_ar"]

    @property
    def effective_fee(self):
        return self.entry_fee if self.entry_fee is not None else self.tournament.entry_fee

    def __str__(self) -> str:
        return f"{self.tournament.name} — {self.name_ar}"


# ============================================================ التسجيل
class Team(TimeStampedModel):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="teams", verbose_name=_("البطولة"))
    category = models.ForeignKey(TournamentCategory, on_delete=models.CASCADE, related_name="teams", verbose_name=_("الفئة"))
    name = models.CharField(_("اسم الفريق"), max_length=120)
    captain = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="captained_teams", verbose_name=_("الكابتن"))
    coach_name = models.CharField(_("اسم المدرب (اختياري)"), max_length=120, blank=True)

    class Meta:
        verbose_name = _("فريق")
        verbose_name_plural = _("الفرق")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TeamMember(TimeStampedModel):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members", verbose_name=_("الفريق"))
    player = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="team_memberships", null=True, blank=True, verbose_name=_("اللاعب"))
    dependent = models.ForeignKey("accounts.Dependent", on_delete=models.CASCADE, related_name="team_memberships", null=True, blank=True, verbose_name=_("التابع"))
    jersey_number = models.PositiveSmallIntegerField(_("رقم القميص"), null=True, blank=True)
    position = models.CharField(_("المركز/الدور"), max_length=40, blank=True)

    class Meta:
        verbose_name = _("لاعب")
        verbose_name_plural = _("اللاعبون")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(player__isnull=False) ^ models.Q(dependent__isnull=False),
                name="teammember_exactly_one_player",
            ),
        ]

    def __str__(self) -> str:
        return self.player.get_full_name() if self.player else (self.dependent.full_name_ar if self.dependent else "؟")


class TournamentRegistration(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("قيد المراجعة")
        ACCEPTED = "accepted", _("مقبول")
        REJECTED = "rejected", _("مرفوض")
        CANCELLED = "cancelled", _("ملغى")

    reference = models.CharField(_("كود التسجيل"), max_length=30, unique=True, blank=True)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="registrations", verbose_name=_("البطولة"))
    category = models.ForeignKey(TournamentCategory, on_delete=models.PROTECT, related_name="registrations", verbose_name=_("الفئة"))
    registered_by = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="tournament_registrations", verbose_name=_("مُسجِّل الطلب"))

    kind = models.CharField(_("نوع التسجيل"), max_length=12, choices=Tournament.RegistrationType.choices)
    team = models.OneToOneField(Team, on_delete=models.CASCADE, null=True, blank=True, related_name="registration", verbose_name=_("الفريق (لو فرقي)"))

    # فردي: اللاعب = العضو أو تابع
    player = models.ForeignKey("accounts.User", on_delete=models.CASCADE, null=True, blank=True, related_name="individual_entries", verbose_name=_("اللاعب"))
    dependent = models.ForeignKey("accounts.Dependent", on_delete=models.CASCADE, null=True, blank=True, related_name="individual_entries", verbose_name=_("التابع"))

    status = models.CharField(_("الحالة"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    fee_amount = models.DecimalField(_("الرسوم (ج)"), max_digits=9, decimal_places=2, default=0)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)
    reviewer_note = models.CharField(_("ملاحظة المراجع"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("تسجيل بطولة")
        verbose_name_plural = _("تسجيلات البطولات")
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"TRN-{timezone.now().year}-{secrets.token_hex(3).upper()}"
        super().save(*args, **kwargs)

    @property
    def player_name(self) -> str:
        if self.kind == Tournament.RegistrationType.TEAM and self.team:
            return self.team.name
        if self.dependent:
            return self.dependent.full_name_ar
        return (self.player.get_full_name() if self.player else "?")

    def __str__(self) -> str:
        return f"{self.reference} — {self.tournament.name}"


# ============================================================ المباريات والترتيب
class Match(TimeStampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", _("قادمة")
        LIVE = "live", _("جارية الآن")
        FINISHED = "finished", _("انتهت")
        POSTPONED = "postponed", _("مؤجلة")

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="matches", verbose_name=_("البطولة"))
    category = models.ForeignKey(TournamentCategory, on_delete=models.CASCADE, related_name="matches", verbose_name=_("الفئة"))
    group_name = models.CharField(_("المجموعة"), max_length=20, blank=True)
    round_name = models.CharField(_("الدور/الجولة"), max_length=40, default=_("الجولة"))

    team_a = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="matches_a", verbose_name=_("الفريق الأول"))
    team_b = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="matches_b", verbose_name=_("الفريق الثاني"))
    team_a_label = models.CharField(_("تسمية الفريق الأول (خروج مغلوب)"), max_length=60, blank=True)
    team_b_label = models.CharField(_("تسمية الفريق الثاني (خروج مغلوب)"), max_length=60, blank=True)

    scheduled_at = models.DateTimeField(_("الموعد"), null=True, blank=True, db_index=True)
    venue = models.CharField(_("الملعب"), max_length=120, blank=True)
    status = models.CharField(_("الحالة"), max_length=12, choices=Status.choices, default=Status.SCHEDULED, db_index=True)

    score_a = models.PositiveSmallIntegerField(_("أهداف/نقاط الأول"), null=True, blank=True)
    score_b = models.PositiveSmallIntegerField(_("أهداف/نقاط الثاني"), null=True, blank=True)
    notes = models.CharField(_("ملاحظات"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("مباراة")
        verbose_name_plural = _("المباريات")
        ordering = ["scheduled_at", "id"]

    @property
    def team_a_name(self) -> str:
        return self.team_a.name if self.team_a else (self.team_a_label or "؟")

    @property
    def team_b_name(self) -> str:
        return self.team_b.name if self.team_b else (self.team_b_label or "؟")

    def __str__(self) -> str:
        return f"{self.team_a_name} × {self.team_b_name} — {self.tournament.name}"


class Standing(TimeStampedModel):
    """ترتيب مجموعة — يُعاد حسابه تلقائيًا عند حفظ أي نتيجة."""

    category = models.ForeignKey(TournamentCategory, on_delete=models.CASCADE, related_name="standings", verbose_name=_("الفئة"))
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="standings", verbose_name=_("الفريق"))
    group_name = models.CharField(_("المجموعة"), max_length=20, default="A")

    played = models.PositiveSmallIntegerField(_("لعب"), default=0)
    won = models.PositiveSmallIntegerField(_("فوز"), default=0)
    drawn = models.PositiveSmallIntegerField(_("تعادل"), default=0)
    lost = models.PositiveSmallIntegerField(_("هزيمة"), default=0)
    goals_for = models.PositiveSmallIntegerField(_("له"), default=0)
    goals_against = models.PositiveSmallIntegerField(_("عليه"), default=0)
    points = models.PositiveSmallIntegerField(_("نقاط"), default=0)

    class Meta:
        verbose_name = _("ترتيب")
        verbose_name_plural = _("الترتيب")
        ordering = ["group_name", "-points", "-goals_for"]
        constraints = [
            models.UniqueConstraint(fields=["category", "team"], name="unique_standing_per_category"),
        ]

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    def __str__(self) -> str:
        return f"{self.team.name} — {self.points} نقطة"


class MatchGoal(TimeStampedModel):
    """هدف في مباراة — للترتيب والهدافين (الألعاب الجماعية فقط)."""

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="goals", verbose_name=_("المباراة"))
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="goals", verbose_name=_("الفريق"))
    scorer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="scored_goals", verbose_name=_("المسجّل"))
    scorer_name = models.CharField(_("اسم المسجّل (نص حر)"), max_length=120, blank=True)
    minute = models.PositiveSmallIntegerField(_("الدقيقة"), null=True, blank=True)
    is_own_goal = models.BooleanField(_("هدف عكسي"), default=False)

    class Meta:
        verbose_name = _("هدف")
        verbose_name_plural = _("الأهداف")

    def __str__(self) -> str:
        return f"{self.scorer_name or self.scorer} ({self.minute or '؟'}')"
