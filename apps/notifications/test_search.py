"""New: notification preferences + global search."""
import pytest

from apps.accounts.models import Profile, User
from apps.events.models import Event
from apps.news.models import NewsArticle, NewsCategory
from apps.notifications.models import NotificationPreference
from apps.tournaments.models import Sport, Tournament
from django.utils import timezone


def _user(phone="01077773001", name="مستلم بحث"):
    u = User.objects.create_user(username=phone, phone=phone, password="pw#12345", is_active=True)
    Profile.objects.create(user=u, full_name_ar=name)
    return u


@pytest.mark.django_db
class TestNotificationPreferences:
    def test_toggle_saves(self, client):
        user = _user()
        client.force_login(user)
        r = client.post("/notifications/preferences/", {"in_app": "on", "whatsapp": "on"})
        assert r.status_code == 302
        pref = NotificationPreference.objects.get(user=user)
        assert pref.in_app is True and pref.whatsapp is True and pref.email is False

    def test_defaults(self, client):
        user = _user()
        client.force_login(user)
        pref = NotificationPreference.objects.get_or_create(user=user)[0]
        assert pref.in_app is True


@pytest.mark.django_db
class TestGlobalSearch:
    def test_search_groups_results(self, client):
        cat = NewsCategory.objects.create(name_ar="بطولات", slug="events")
        NewsArticle.objects.create(title="بطولة الربيع تنطلق", category=cat, status=NewsArticle.Status.PUBLISHED)
        sport = Sport.objects.create(name_ar="كرة قدم", is_team_sport=True)
        Tournament.objects.create(name="بطولة الربيع الخماسية", sport=sport, status=Tournament.Status.REGISTRATION)
        Event.objects.create(title="يوم مفتوح في حمام السباحة", status=Event.Status.PUBLISHED, start_at=timezone.now() + timezone.timedelta(days=3))

        response = client.get("/search/?q=الربيع")
        assert response.status_code == 200
        body = response.content.decode()
        assert "بطولة الربيع تنطلق" in body
        assert "بطولة الربيع الخماسية" in body
        assert "الأخبار" in body and "البطولات" in body

    def test_search_too_short_returns_no_results(self, client):
        response = client.get("/search/?q=x")
        assert response.status_code == 200

    def test_search_no_results_page(self, client):
        response = client.get("/search/?q=زززززز")
        assert response.status_code == 200
