"""Tournament services: fixtures generation, standings, registration rules."""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Match, MatchGoal, Sport, Standing, Team, TournamentCategory, TournamentRegistration


# ---------------------------------------------------------- fixtures

def generate_round_robin(category: TournamentCategory, *, clear_existing: bool = False, dry_run: bool = False) -> list[Match]:
    """
    جدول Round Robin لمرة واحدة (الكل × الكل). يضيف البلاي-بايز للمنافس الفردي.
    clear_existing=True يمسح كل مباريات الفئة قبل التوليد (IRREVERSIBLE).
    """
    teams = list(Team.objects.filter(category=category))
    if len(teams) < 2:
        return []

    if clear_existing:
        Match.objects.filter(category=category, status=Match.Status.SCHEDULED).delete()

    ids = [t.id for t in teams]
    if len(ids) % 2:
        ids.append(None)  # bye — الأسبوع الحر

    order = ids[:]
    n = len(order)
    rounds = n - 1
    half = n // 2
    fixtures = []
    for r in range(rounds):
        for i in range(half):
            a, b = order[i], order[n - 1 - i]
            if a is not None and b is not None:
                fixtures.append((a, b, r + 1))
        order = [order[0]] + [order[-1]] + order[1:-1]  # تدوير Berger

    created = []
    if dry_run:
        return [Match(category=category, tournament=category.tournament, team_a_id=a, team_b_id=b, round_name=_("الجولة %(r)s") % {"r": r}, group_name=category.name_ar[:20]) for a, b, r in fixtures]

    with transaction.atomic():
        for a_id, b_id, round_no in fixtures:
            match, _created = Match.objects.get_or_create(
                category=category,
                tournament=category.tournament,
                team_a_id=a_id,
                team_b_id=b_id,
                defaults={"round_name": _("الجولة %(r)s") % {"r": round_no}, "group_name": "A"},
            )
            created.append(match)
    return created


def ensure_standings(category: TournamentCategory) -> None:
    for team in Team.objects.filter(category=category):
        Standing.objects.get_or_create(category=category, team=team, defaults={"group_name": "A"})


def recompute_standings(category: TournamentCategory) -> None:
    """أعد الحساب من الصفر — يعتمد على المباريات «انتهت» فقط."""
    ensure_standings(category)
    rows = {s.team_id: s for s in Standing.objects.filter(category=category)}
    for s in rows.values():
        s.played = s.won = s.drawn = s.lost = 0
        s.goals_for = s.goals_against = s.points = 0

    matches = Match.objects.filter(category=category, status=Match.Status.FINISHED, team_a__isnull=False, team_b__isnull=False)
    for m in matches:
        a, b = rows[m.team_a_id], rows[m.team_b_id]
        a.played += 1
        b.played += 1
        a.goals_for += m.score_a or 0
        a.goals_against += m.score_b or 0
        b.goals_for += m.score_b or 0
        b.goals_against += m.score_a or 0
        if (m.score_a or 0) > (m.score_b or 0):
            a.won += 1
            b.lost += 1
            a.points += 3
        elif (m.score_a or 0) < (m.score_b or 0):
            b.won += 1
            a.lost += 1
            b.points += 3
        else:
            a.drawn += 1
            b.drawn += 1
            a.points += 1
            b.points += 1

    with transaction.atomic():
        for s in rows.values():
            s.save(update_fields=["played", "won", "drawn", "lost", "goals_for", "goals_against", "points"])


def top_scorers(category: TournamentCategory, limit: int = 5):
    """هدافو الفئة — حسب الأهداف المسجلة (بدون أهداف عكسية). ترجع [{name, goals}]."""
    rows = (
        MatchGoal.objects.filter(match__category=category, is_own_goal=False)
        .select_related("scorer")
        .values("scorer", "scorer_name")
        .annotate(goals=Count("id"))
        .order_by("-goals")[:limit]
    )
    out = []
    for row in rows:
        scorer_name = row["scorer_name"]
        if not scorer_name and row["scorer"]:
            from apps.accounts.models import User

            try:
                u = User.objects.get(pk=row["scorer"])
                scorer_name = u.get_full_name() or u.phone
            except User.DoesNotExist:
                scorer_name = "—"
        out.append({"name": scorer_name or "—", "goals": row["goals"]})
    return out


# ------------------------------------------------------ registration

@dataclass
class RegistrationCheck:
    ok: bool
    message: str


def check_age(category: TournamentCategory, birth_date) -> RegistrationCheck:
    if birth_date is None:
        return RegistrationCheck(False, _("أضف تاريخ الميلاد في ملفك أولًا."))
    today = timezone.now().date()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    if age < category.age_min or age > category.age_max:
        return RegistrationCheck(False, _("سن اللاعب (%(age)s سنة) غير مناسب لهذه الفئة.") % {"age": age})
    return RegistrationCheck(True, "")


def _check_gender(category: TournamentCategory, gender: str) -> None | str:
    if category.gender != TournamentCategory.Gender.MIXED and gender and gender != category.gender:
        return _("هذه الفئة مخصصة للنوع المحدد فقط.")
    return None


def register_player(*, user, tournament, category, for_user: bool, dependent=None) -> tuple[TournamentRegistration | None, str | None]:
    """تسجيل فردي — يتحقق من السن والفئة والنوع والمقاعد المتاحة."""
    if tournament.registration_type != tournament.RegistrationType.INDIVIDUAL:
        return None, _("هذه البطولة للفرق — استخدم تسجيل الفرق.")
    if tournament.seats_left <= 0:
        return None, _("اكتمل العدد.")

    if for_user:
        profile = getattr(user, "profile", None)
        birth = profile.birth_date if profile else None
        gender = profile.gender if profile else ""
        name_ar = profile.full_name_ar if profile else user.get_full_name()
    else:
        if dependent is None or dependent.guardian_id != user.id:
            return None, _("يمكنك التسجيل لنفسك أو لتابعيك فقط.")
        birth, gender, name_ar = dependent.birth_date, dependent.gender, dependent.full_name_ar

    check = check_age(category, birth)
    if not check.ok:
        return None, check.message
    gender_error = _check_gender(category, gender)
    if gender_error:
        return None, gender_error

    registration = TournamentRegistration.objects.create(
        tournament=tournament,
        category=category,
        registered_by=user,
        kind=tournament.RegistrationType.INDIVIDUAL,
        player=user if for_user else None,
        dependent=None if for_user else dependent,
        fee_amount=category.effective_fee or 0,
    )
    return registration, None


def register_team(*, user, tournament, category, team_name: str, member_dependents: list | None = None, coach_name: str = "") -> tuple[TournamentRegistration | None, str | None]:
    """تسجيل فريق: الكبتن (المستخدم) + تابعينه — نفس فئة السن."""
    if tournament.registration_type != tournament.RegistrationType.TEAM:
        return None, _("هذه البطولة تسجيل فردي — استخدم تسجيل الأفراد.")
    if tournament.seats_left <= 0:
        return None, _("اكتمل عدد الفرق.")

    dependents = list(member_dependents or [])
    if any(d.guardian_id != user.id for d in dependents):
        return None, _("اللاعبون في قائمتك يجب أن يكونوا تابعيك.")

    profile = getattr(user, "profile", None)
    captain_birth = profile.birth_date if profile else None
    check = check_age(category, captain_birth)
    if not check.ok:
        return None, check.message
    for dep in dependents:
        c = check_age(category, dep.birth_date)
        if not c.ok:
            return None, c.message

    if len(dependents) + 1 > tournament.squad_size:
        return None, _("تجاوزت الحد الأقصى للاعبين في القائمة.")

    with transaction.atomic():
        team = Team.objects.create(tournament=tournament, category=category, name=team_name.strip()[:120], captain=user, coach_name=coach_name.strip()[:120])
        from .models import TeamMember

        TeamMember.objects.create(team=team, player=user)
        for dep in dependents:
            TeamMember.objects.create(team=team, dependent=dep)
        registration = TournamentRegistration.objects.create(
            tournament=tournament,
            category=category,
            registered_by=user,
            kind=tournament.RegistrationType.TEAM,
            team=team,
            fee_amount=category.effective_fee or 0,
        )
    return registration, None
