"""Sitemaps — SEO للصفحات العامة."""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["core:home", "pages:about", "pages:facilities", "pages:pricing", "pages:regulation", "pages:faq", "pages:contact", "pages:learn_more", "news:list", "events:list", "tournaments:list", "courses:list", "trips:list", "gallery:list"]

    def location(self, item):
        return reverse(item)


class NewsSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        from django.db.models import Q
        from django.utils import timezone

        from apps.news.models import NewsArticle

        now = timezone.now()
        return NewsArticle.objects.filter(
            Q(status=NewsArticle.Status.PUBLISHED) | Q(status=NewsArticle.Status.SCHEDULED, published_at__lte=now)
        ).order_by("-published_at")

    def lastmod(self, obj):
        return obj.updated_at


class EventsSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7

    def items(self):
        from apps.events.models import Event

        return Event.objects.filter(status=Event.Status.PUBLISHED).order_by("start_at")

    def lastmod(self, obj):
        return obj.updated_at


class TournamentsSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        from apps.tournaments.models import Tournament

        return Tournament.objects.exclude(status=Tournament.Status.DRAFT).order_by("-created_at")

    def lastmod(self, obj):
        return obj.updated_at


class CoursesSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        from apps.courses.models import Course

        return Course.objects.exclude(status=Course.Status.DRAFT).order_by("-created_at")

    def lastmod(self, obj):
        return obj.updated_at


class TripsSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        from apps.trips.models import Trip

        return Trip.objects.exclude(status=Trip.Status.DRAFT).order_by("trip_date")

    def lastmod(self, obj):
        return obj.updated_at
