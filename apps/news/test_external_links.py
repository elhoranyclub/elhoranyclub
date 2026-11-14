"""لينك خارجي اختياري للمحتوى (خبر · نشاط · دورة · رحلة · بطولة)."""
import pytest
from django.urls import reverse

from apps.courses.models import Course
from apps.events.models import Event
from apps.news.models import NewsArticle, NewsCategory
from apps.tournaments.models import Tournament
from apps.trips.models import Trip


@pytest.mark.django_db
def test_external_link_is_optional_and_hidden_when_empty(client):
    """من غير لينك — مفيش زرار في الصفحة."""
    cat = NewsCategory.objects.create(name_ar="أخبار", slug="akhbar")
    article = NewsArticle.objects.create(
        title="خبر بدون لينك", slug="no-link", category=cat, status=NewsArticle.Status.PUBLISHED
    )
    assert article.external_url == ""
    response = client.get(article.get_absolute_url())
    body = response.content.decode()
    assert response.status_code == 200
    assert "افتح الرابط الخارجي" not in body


@pytest.mark.django_db
def test_external_link_button_shows_when_set(client):
    """مع لينك — بيظهر زرار بالنص المخصص."""
    cat = NewsCategory.objects.create(name_ar="أخبار", slug="akhbar2")
    article = NewsArticle.objects.create(
        title="برنامج الوزارة",
        slug="with-link",
        category=cat,
        status=NewsArticle.Status.PUBLISHED,
        external_url="https://example.gov.eg/program",
        external_label="رابط البرنامج على موقع الوزارة",
    )
    response = client.get(article.get_absolute_url())
    body = response.content.decode()
    assert response.status_code == 200
    assert "https://example.gov.eg/program" in body
    assert "رابط البرنامج على موقع الوزارة" in body
    assert 'target="_blank"' in body
    assert "rel=\"noopener noreferrer\"" in body


@pytest.mark.django_db
def test_all_content_types_have_the_field():
    """كل أنواع المحتوى بتقبل لينك خارجي."""
    import datetime

    assert hasattr(NewsArticle, "external_url")
    assert hasattr(Event, "external_url")
    assert hasattr(Course, "external_url")
    assert hasattr(Trip, "external_url")
    assert hasattr(Tournament, "external_url")

    trip = Trip.objects.create(
        name="رحلة اختبار",
        slug="trip-link-test",
        destination="الساحل",
        trip_date=datetime.date.today() + datetime.timedelta(days=10),
        external_url="https://example.gov.eg/trip",
    )
    assert trip.external_url == "https://example.gov.eg/trip"


@pytest.mark.django_db
def test_manage_form_exposes_the_field(client):
    """شاشة الإدارة تعرض الخانتين — يقدر الأدمن يحط اللينك."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    admin = User.objects.create_superuser(
        "01011119999", "admin@example.com", "x", phone="01011119999"
    )
    client.force_login(admin)

    response = client.get(reverse("core:manage_create", args=["news", "newsarticle"]))
    body = response.content.decode()
    assert response.status_code == 200
    assert "external_url" in body
    assert "external_label" in body
