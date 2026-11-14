from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("news", views.NewsArticleViewSet, basename="news")
router.register("events", views.EventViewSet, basename="event")
router.register("tournaments", views.TournamentViewSet, basename="tournament")
router.register("courses", views.CourseViewSet, basename="course")
router.register("trips", views.TripViewSet, basename="trip")
router.register("membership-types", views.MembershipTypeViewSet, basename="membership-type")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/", include("rest_framework.urls")),
]
