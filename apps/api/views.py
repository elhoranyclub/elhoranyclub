"""API views — قراءة عامة فقط الآن. الكتابة/التسجيل يصل في مراحل لاحقة."""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.courses.models import Course
from apps.events.models import Event
from apps.memberships.models import MembershipType
from apps.news.models import NewsArticle
from apps.tournaments.models import Tournament
from apps.trips.models import Trip

from .serializers import (
    CourseSerializer,
    EventSerializer,
    MembershipTypeSerializer,
    NewsArticleDetailSerializer,
    NewsArticleListSerializer,
    TournamentSerializer,
    TripSerializer,
)


class NewsArticleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NewsArticle.objects.filter(status=NewsArticle.Status.PUBLISHED).select_related("category")
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        return NewsArticleDetailSerializer if self.action == "retrieve" else NewsArticleListSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.filter(status=Event.Status.PUBLISHED).order_by("start_at")
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = EventSerializer


class TournamentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tournament.objects.exclude(status=Tournament.Status.DRAFT).select_related("sport").prefetch_related("categories")
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = TournamentSerializer


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Course.objects.exclude(status=Course.Status.DRAFT).select_related("sport", "coach")
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = CourseSerializer


class TripViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Trip.objects.exclude(status=Trip.Status.DRAFT).order_by("trip_date")
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = TripSerializer


class MembershipTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MembershipType.objects.filter(is_active=True)
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = MembershipTypeSerializer
