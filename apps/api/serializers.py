"""DRF serializers — قراءة عامة للقراءة فقط (المراحل الأساسية للتطبيق لاحقًا)."""
from rest_framework import serializers

from apps.courses.models import Course
from apps.events.models import Event
from apps.memberships.models import MembershipType
from apps.news.models import NewsArticle, NewsCategory
from apps.tournaments.models import Tournament, TournamentCategory
from apps.trips.models import Trip


class NewsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsCategory
        fields = ["name_ar", "name_en", "slug"]


class NewsArticleListSerializer(serializers.ModelSerializer):
    category = NewsCategorySerializer(read_only=True)

    class Meta:
        model = NewsArticle
        fields = ["title", "title_en", "slug", "summary", "cover", "category", "published_at", "is_featured"]


class NewsArticleDetailSerializer(NewsArticleListSerializer):
    content = serializers.CharField(read_only=True)

    class Meta(NewsArticleListSerializer.Meta):
        fields = NewsArticleListSerializer.Meta.fields + ["content"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["title", "title_en", "slug", "description", "start_at", "end_at", "location", "image",
                  "capacity", "is_free", "price", "min_age", "max_age", "requires_registration"]


class TournamentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TournamentCategory
        fields = ["name_ar", "name_en", "gender", "age_min", "age_max"]


class TournamentSerializer(serializers.ModelSerializer):
    sport = serializers.CharField(source="sport.name_ar", read_only=True)
    sport_slug = serializers.CharField(source="sport.name_en", read_only=True)
    categories = TournamentCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Tournament
        fields = ["name", "name_en", "slug", "sport", "sport_slug", "description", "start_date", "end_date",
                  "registration_start", "registration_end", "registration_type", "format", "max_teams",
                  "entry_fee", "status", "cover", "categories"]


class CourseSerializer(serializers.ModelSerializer):
    sport = serializers.CharField(source="sport.name_ar", read_only=True)
    coach = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ["name", "name_en", "slug", "sport", "coach", "level", "gender", "age_min", "age_max",
                  "schedule", "location", "start_date", "duration_weeks", "price", "price_type", "capacity", "status"]

    def get_coach(self, obj):
        return obj.coach.get_full_name() if obj.coach else None


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ["name", "name_en", "slug", "destination", "description", "trip_date", "meeting_point",
                  "meeting_time", "member_price", "guest_price", "capacity", "status", "cover"]


class MembershipTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipType
        fields = ["name_ar", "name_en", "description", "price", "duration_months", "min_age", "max_age"]
