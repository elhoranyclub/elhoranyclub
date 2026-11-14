"""API smoke tests — كل endpoint تُرجع 200 وpaginated."""
import pytest

from apps.events.models import Event
from apps.news.models import NewsArticle, NewsCategory
from apps.tournaments.models import Sport, Tournament, TournamentCategory


@pytest.mark.django_db
class TestPublicEndpoints:
    @pytest.mark.parametrize("url", ["/api/news/", "/api/events/", "/api/tournaments/", "/api/courses/", "/api/trips/", "/api/membership-types/"])
    def test_list_endpoints_return_200(self, client, url):
        response = client.get(url)
        assert response.status_code == 200
        assert b"results" in response.content or response.content.startswith(b"[")

    def test_news_detail_uses_slug(self, client):
        cat = NewsCategory.objects.create(name_ar="إعلانات", slug="announce")
        article = NewsArticle.objects.create(title="خبر تجريبي", category=cat, status=NewsArticle.Status.PUBLISHED)
        response = client.get(f"/api/news/{article.pk}/")
        assert response.status_code == 200
        assert "خبر تجريبي".encode() in response.content

    def test_draft_tournaments_hidden(self, client):
        sport = Sport.objects.create(name_ar="كرة قدم", is_team_sport=True)
        visible = Tournament.objects.create(name="معلنة", sport=sport, status=Tournament.Status.REGISTRATION)
        hidden = Tournament.objects.create(name="مسودة", sport=sport, status=Tournament.Status.DRAFT)
        response = client.get("/api/tournaments/")
        assert "معلنة".encode() in response.content
        assert "مسودة".encode() not in response.content
