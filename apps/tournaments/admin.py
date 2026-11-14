from django.contrib import admin

from .models import (
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


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "is_team_sport", "order")
    list_editable = ("is_team_sport", "order")


class CategoryInline(admin.TabularInline):
    model = TournamentCategory
    extra = 1


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ("name", "sport", "status", "registration_type", "format", "start_date", "entry_fee")
    list_filter = ("status", "registration_type", "format", "sport")
    search_fields = ("name", "name_en")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryInline]


@admin.register(TournamentCategory)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "tournament", "gender", "age_min", "age_max", "entry_fee")
    list_filter = ("tournament",)


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    readonly_fields = ("player", "dependent", "jersey_number", "position")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "tournament", "category", "captain")
    search_fields = ("name", "captain__phone")
    list_filter = ("tournament", "category")
    inlines = [TeamMemberInline]


@admin.register(TournamentRegistration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("reference", "tournament", "category", "player_name", "status", "fee_amount", "created_at")
    list_filter = ("status", "kind", "tournament")
    search_fields = ("reference", "team__name", "player__phone", "registered_by__phone")
    readonly_fields = ("reference", "created_at", "updated_at")
    actions = ["accept", "reject"]

    @admin.action(description="قبول المحدد")
    def accept(self, request, queryset):
        queryset.update(status=TournamentRegistration.Status.ACCEPTED)

    @admin.action(description="رفض المحدد")
    def reject(self, request, queryset):
        queryset.update(status=TournamentRegistration.Status.REJECTED)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("__str__", "round_name", "scheduled_at", "status", "score_a", "score_b")
    list_filter = ("status", "tournament", "category", "round_name")
    search_fields = ("team_a__name", "team_b__name", "venue")
    date_hierarchy = "scheduled_at"


@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = ("team", "category", "group_name", "played", "won", "drawn", "lost", "goals_for", "goals_against", "points")
    list_filter = ("category",)
    readonly_fields = [f.name for f in Standing._meta.fields]


@admin.register(MatchGoal)
class MatchGoalAdmin(admin.ModelAdmin):
    list_display = ("__str__", "match", "team", "minute", "is_own_goal")
    list_filter = ("match__tournament",)
