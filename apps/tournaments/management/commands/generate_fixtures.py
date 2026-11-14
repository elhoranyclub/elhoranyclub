"""Generate Round Robin fixtures for a tournament: python manage.py generate_fixtures <slug> [--clear]"""
from django.core.management.base import BaseCommand, CommandError

from apps.tournaments.models import Tournament, TournamentCategory
from apps.tournaments.services import ensure_standings, generate_round_robin, recompute_standings


class Command(BaseCommand):
    help = "ولّد جدول Round Robin لفئات بطولة (مع --clear لمسح المباريات القادمة وإعادة التوليد)."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--clear", action="store_true")

    def handle(self, *args, **options):
        try:
            tournament = Tournament.objects.prefetch_related("categories").get(slug=options["slug"])
        except Tournament.DoesNotExist as exc:
            raise CommandError("البطولة غير موجودة") from exc

        for category in tournament.categories.all():
            ensure_standings(category)
            fixtures = generate_round_robin(category, clear_existing=options["clear"])
            recompute_standings(category)
            self.stdout.write(f"[{category.name_ar}] teams -> {len(fixtures)} fixtures")
        self.stdout.write(self.style.SUCCESS("Fixtures OK"))
