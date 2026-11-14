"""Tournaments views — القائمة، التفاصيل، التسجيل، النتائج، اللايف."""
from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import Match, Sport, Standing, Tournament, TournamentCategory, TournamentRegistration
from .services import (
    check_age,
    generate_round_robin,
    recompute_standings,
    register_player,
    register_team,
    top_scorers,
)


def _staff_required(user):
    return user.is_authenticated and user.is_staff


def tournament_list(request):
    tab = request.GET.get("tab", "registration")
    base = Tournament.objects.select_related("sport")
    tabs = {
        "registration": base.filter(status=Tournament.Status.REGISTRATION),
        "ongoing": base.filter(status=Tournament.Status.ONGOING),
        "finished": base.filter(status=Tournament.Status.FINISHED),
    }
    tournaments = tabs.get(tab, tabs["registration"])
    return render(request, "tournaments/list.html", {"tournaments": tournaments, "tab": tab, "sports": Sport.objects.all()})


def tournament_detail(request, slug):
    tournament = get_object_or_404(Tournament.objects.select_related("sport").prefetch_related("categories"), slug=slug)
    tab = request.GET.get("tab", "overview")
    categories = list(tournament.categories.all())
    matches = tournament.matches.select_related("team_a", "team_b", "category").order_by("scheduled_at", "id")[:60]
    standings = {cat.id: list(Standing.objects.filter(category=cat).select_related("team").order_by("group_name", "-points", "-goals_for")) for cat in categories}
    scorers = {cat.id: list(top_scorers(cat, 5)) for cat in categories}

    my_registration = None
    if request.user.is_authenticated:
        my_registration = TournamentRegistration.objects.filter(tournament=tournament, registered_by=request.user).exclude(status=TournamentRegistration.Status.CANCELLED).first()

    return render(request, "tournaments/detail.html", {
        "tournament": tournament,
        "tab": tab,
        "categories": categories,
        "matches": matches,
        "standings": standings,
        "scorers": scorers,
        "my_registration": my_registration,
        "meta_description": (tournament.description or tournament.name)[:160],
    })


@login_required
def register(request, slug):
    tournament = get_object_or_404(Tournament.objects.prefetch_related("categories"), slug=slug)
    if not tournament.is_registration_open:
        messages.error(request, _("باب التسجيل مغلق لهذه البطولة."))
        return redirect(tournament.get_absolute_url())

    profile = getattr(request.user, "profile", None)
    if tournament.registration_type == Tournament.RegistrationType.INDIVIDUAL:
        targets = [("self", (profile.full_name_ar if profile else request.user.get_full_name()), profile.birth_date if profile else None, profile.gender if profile else "")]
        for dep in request.user.dependents.all():
            targets.append((f"dep:{dep.pk}", dep.full_name_ar, dep.birth_date, dep.gender))
    else:
        targets = []
        for dep in request.user.dependents.all():
            targets.append((f"dep:{dep.pk}", dep.full_name_ar, dep.birth_date, dep.gender))

    if request.method == "POST":
        category_id = request.POST.get("category")
        category = get_object_or_404(TournamentCategory, pk=category_id, tournament=tournament)

        if tournament.registration_type == Tournament.RegistrationType.INDIVIDUAL:
            who = request.POST.get("player", "self")
            if who == "self":
                registration, err = register_player(user=request.user, tournament=tournament, category=category, for_user=True)
            else:
                dep_id = int(who.split(":", 1)[1])
                from apps.accounts.models import Dependent

                dependent = get_object_or_404(Dependent, pk=dep_id, guardian=request.user)
                registration, err = register_player(user=request.user, tournament=tournament, category=category, for_user=False, dependent=dependent)
        else:
            team_name = (request.POST.get("team_name") or "").strip()
            if not team_name:
                messages.error(request, _("اكتب اسم الفريق."))
                return redirect("tournaments:register", slug=slug)
            dep_ids = [int(pk) for pk in request.POST.getlist("members")]
            from apps.accounts.models import Dependent

            dependents = list(Dependent.objects.filter(pk__in=dep_ids, guardian=request.user))
            registration, err = register_team(
                user=request.user, tournament=tournament, category=category,
                team_name=team_name, member_dependents=dependents,
                coach_name=(request.POST.get("coach_name") or "").strip(),
            )

        if err:
            messages.error(request, err)
            return redirect("tournaments:register", slug=slug)

        fee = registration.category.effective_fee or 0
        if fee > 0:
            from apps.payments.models import Payment
            from apps.payments.services import create_payment

            payment = create_payment(
                member=request.user,
                amount=fee,
                kind=Payment.Kind.TOURNAMENT,
                method=Payment.Method.ONLINE,
                tournament_registration=registration,
                note=f"رسوم تسجيل {tournament.name}",
            )
            messages.info(request, _("أكمل الدفع خلال 48 ساعة لتأكيد تسجيلك."))
            return redirect("payments:checkout", reference=payment.reference)

        registration.status = TournamentRegistration.Status.ACCEPTED
        registration.save(update_fields=["status"])
        messages.success(request, _("تم تأكيد تسجيلك — نتمنى لك بطولة موفقة!"))
        return redirect("tournaments:my_registrations")

    return render(request, "tournaments/register.html", {
        "tournament": tournament,
        "categories": tournament.categories.all(),
        "targets": targets,
        "dependents": request.user.dependents.all(),
        "profile": profile,
    })


@login_required
def my_registrations(request):
    registrations = TournamentRegistration.objects.filter(registered_by=request.user).select_related(
        "tournament", "category", "team"
    ).order_by("-created_at")
    from apps.payments.models import Payment

    payments = {p.tournament_registration_id: p for p in Payment.objects.filter(
        tournament_registration__in=registrations
    ).exclude(status=Payment.Status.FAILED)}
    return render(request, "tournaments/my_registrations.html", {"registrations": registrations, "payments": payments})


@user_passes_test(_staff_required, login_url="accounts:login")
@require_POST
def staff_set_status(request: HttpRequest, registration_id: int, action: str) -> HttpResponse:
    registration = get_object_or_404(TournamentRegistration.objects.select_related("tournament"), pk=registration_id)
    if action == "accept":
        registration.status = TournamentRegistration.Status.ACCEPTED
        messages.success(request, _("تم قبول التسجيل."))
    else:
        registration.status = TournamentRegistration.Status.REJECTED
        registration.reviewer_note = (request.POST.get("note") or "").strip()[:255]
        messages.info(request, _("تم رفض التسجيل."))
    registration.save(update_fields=["status", "reviewer_note"])
    return redirect("tournaments:detail", slug=registration.tournament.slug)


@user_passes_test(_staff_required, login_url="accounts:login")
@require_POST
def enter_result(request: HttpRequest, match_id: int) -> HttpResponse:
    match = get_object_or_404(Match.objects.select_related("category"), pk=match_id)
    try:
        score_a = int(request.POST.get("score_a"))
        score_b = int(request.POST.get("score_b"))
    except (TypeError, ValueError):
        messages.error(request, _("النتيجة أرقام فقط."))
        return redirect("tournaments:manage_matches", slug=match.tournament.slug)

    match.score_a, match.score_b = score_a, score_b
    match.status = Match.Status.FINISHED
    match.save(update_fields=["score_a", "score_b", "status", "updated_at"])
    recompute_standings(match.category)
    messages.success(request, _("تم حفظ النتيجة وتحديث الترتيب."))
    return redirect("tournaments:manage_matches", slug=match.tournament.slug)


@user_passes_test(_staff_required, login_url="accounts:login")
def manage_matches(request):
    slug = request.GET.get("slug")
    tournament = get_object_or_404(Tournament, slug=slug) if slug else Tournament.objects.filter(status__in=[Tournament.Status.REGISTRATION, Tournament.Status.ONGOING]).first()
    matches = []
    if tournament:
        matches = tournament.matches.select_related("team_a", "team_b", "category").order_by("scheduled_at", "id")
    return render(request, "tournaments/manage_matches.html", {"tournament": tournament, "matches": matches})


def live(request):
    live_matches = Match.objects.filter(status=Match.Status.LIVE).select_related("team_a", "team_b", "category", "tournament")
    today_finished = Match.objects.filter(status=Match.Status.FINISHED, scheduled_at__date=timezone.now().date()).select_related("team_a", "team_b", "tournament")
    context = {"live_matches": live_matches, "today_finished": today_finished}
    if getattr(request, "htmx", None):
        return render(request, "tournaments/_live_partial.html", context)
    return render(request, "tournaments/live.html", context)
