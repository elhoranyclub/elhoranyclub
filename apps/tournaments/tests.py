"""Critical tournament paths: fixtures generation, standings, registration."""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Dependent, Profile, User
from apps.tournaments.models import (
    Match,
    MatchGoal,
    Sport,
    Standing,
    Team,
    TeamMember,
    Tournament,
    TournamentCategory,
    TournamentRegistration,
)
from apps.tournaments.services import (
    check_age,
    generate_round_robin,
    recompute_standings,
    register_player,
    register_team,
    top_scorers,
)


def _user(phone="01077770001", name="كابتن ديمو"):
    u = User.objects.create_user(username=phone, phone=phone, password="pw#12345", is_active=True, first_name=name.split()[0], last_name=name.split()[-1])
    Profile.objects.create(user=u, full_name_ar=name, birth_date=date(2013, 6, 1), gender="M")
    return u


def _tournament(fee=0):
    sport = Sport.objects.create(name_ar="كرة القدم", is_team_sport=True)
    tournament = Tournament.objects.create(
        name="بطولة اختبار",
        sport=sport,
        registration_type=Tournament.RegistrationType.TEAM,
        format=Tournament.Format.LEAGUE,
        status=Tournament.Status.REGISTRATION,
        entry_fee=Decimal(str(fee)),
    )
    category = TournamentCategory.objects.create(tournament=tournament, name_ar="تحت 14", age_min=10, age_max=14, gender="M")
    return tournament, category


@pytest.mark.django_db
class TestFixtures:
    def test_round_robin_four_teams_produces_six_fixtures(self):
        tournament, category = _tournament()
        captains = [_user(f"010777700{i:02d}", f"كبتن {i}") for i in range(2, 6)]
        for i, captain in enumerate(captains):
            Team.objects.create(tournament=tournament, category=category, name=f"فريق {i}", captain=captain)
        fixtures = generate_round_robin(category)
        assert len(fixtures) == 6
        pairs = {tuple(sorted((f.team_a_id, f.team_b_id))) for f in fixtures}
        assert len(pairs) == 6

    def test_standings_recomputed_from_results(self):
        tournament, category = _tournament()
        captains = [_user(f"010777701{i:02d}", f"كبتن {i}") for i in range(2, 6)]
        teams = [Team.objects.create(tournament=tournament, category=category, name=f"فريق {i}", captain=captains[i]) for i in range(4)]
        m1 = Match.objects.create(tournament=tournament, category=category, team_a=teams[0], team_b=teams[1], score_a=2, score_b=0, status=Match.Status.FINISHED, round_name="الجولة 1")
        m2 = Match.objects.create(tournament=tournament, category=category, team_a=teams[2], team_b=teams[3], score_a=1, score_b=1, status=Match.Status.FINISHED, round_name="الجولة 1")
        recompute_standings(category)
        standings = list(Standing.objects.filter(category=category).order_by("-points", "-goals_for"))
        assert standings[0].team == teams[0]
        assert standings[0].points == 3
        assert standings[1].points == 1 and standings[2].points == 1
        assert standings[3].points == 0


@pytest.mark.django_db
class TestRegistration:
    def test_age_check_rejects_out_of_range(self):
        tournament, category = _tournament()
        old_user = User.objects.create_user(username="01077770201", phone="01077770201", password="pw#12345", is_active=True)
        Profile.objects.create(user=old_user, full_name_ar="كبير", birth_date=date(1980, 1, 1), gender="M")
        check = check_age(category, old_user.profile.birth_date)
        assert not check.ok

    def test_register_player_valid(self):
        tournament, category = _tournament()
        tournament.registration_type = Tournament.RegistrationType.INDIVIDUAL
        tournament.save(update_fields=["registration_type"])
        user = _user()
        registration, err = register_player(user=user, tournament=tournament, category=category, for_user=True)
        assert err is None
        assert registration.status == TournamentRegistration.Status.PENDING

    def test_register_team_creates_team_and_members(self):
        tournament, category = _tournament()
        user = _user()
        dep = Dependent.objects.create(guardian=user, full_name_ar="ابن ديمو", birth_date=date(2012, 5, 1), gender="M", relation="son")
        registration, err = register_team(
            user=user, tournament=tournament, category=category,
            team_name="نجوم الحوراني", member_dependents=[dep],
        )
        assert err is None
        assert registration.team.name == "نجوم الحوراني"
        assert TeamMember.objects.filter(team=registration.team).count() == 2


@pytest.mark.django_db
class TestScorers:
    def test_top_scorers_counts_goals(self):
        tournament, category = _tournament()
        user = _user()
        other = _user("01077770302", "لاعب آخر")
        team_a = Team.objects.create(tournament=tournament, category=category, name="أ", captain=user)
        team_b = Team.objects.create(tournament=tournament, category=category, name="ب", captain=other)
        match = Match.objects.create(tournament=tournament, category=category, team_a=team_a, team_b=team_b, score_a=3, score_b=1, status=Match.Status.FINISHED)
        MatchGoal.objects.create(match=match, team=team_a, scorer=user, minute=10)
        MatchGoal.objects.create(match=match, team=team_a, scorer=user, minute=30)
        MatchGoal.objects.create(match=match, team=team_b, scorer=other, minute=50)
        scorers = top_scorers(category)
        assert scorers[0]["name"] == user.get_full_name()
        assert scorers[0]["goals"] == 2
