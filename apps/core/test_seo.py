# -*- coding: utf-8 -*-
"""فحص SEO: robots · sitemap · canonical · JSON-LD · بيانات جوجل."""
import re

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_robots_txt_allows_public_and_blocks_private(client):
    r = client.get("/robots.txt")
    body = r.content.decode()
    assert r.status_code == 200
    assert "User-agent: *" in body
    assert "Sitemap:" in body
    assert "/admin/" in body
    assert "/dashboard/" in body
    # الصفحة الرئيسية لازم تكون مسموحة (مفيش Disallow للروت)
    assert "\nDisallow: /\n" not in body


@pytest.mark.django_db
def test_sitemap_contains_public_pages(client):
    r = client.get("/sitemap.xml")
    body = r.content.decode()
    assert r.status_code == 200
    assert "<urlset" in body
    assert "/news/" in body
    assert "/tournaments/" in body
    assert "/courses/" in body
    assert "/trips/" in body
    assert "/pages/pricing/" in body
    assert "/pages/contact/" in body


@pytest.mark.django_db
def test_home_has_canonical_and_json_ld(client):
    r = client.get("/")
    body = r.content.decode()
    assert r.status_code == 200
    assert 'rel="canonical"' in body
    assert "application/ld+json" in body
    # بيانات المركز
    assert "SportsActivityLocation" in body
    assert "LocalBusiness" in body
    assert "دمياط" in body or "فارسكور" in body
    assert 'name="robots"' in body
    assert "index, follow" in body


@pytest.mark.django_db
def test_article_page_has_article_schema(client):
    from apps.news.models import NewsArticle, NewsCategory

    cat = NewsCategory.objects.create(name_ar="أخبار", slug="seo-akhbar")
    article = NewsArticle.objects.create(
        title="خبر للاختبار", slug="seo-article", category=cat,
        status=NewsArticle.Status.PUBLISHED, summary="ملخص الخبر",
    )
    r = client.get(article.get_absolute_url())
    body = r.content.decode()
    assert r.status_code == 200
    assert '"@type": "Article"' in body or '"@type":"Article"' in body
    assert "خبر للاختبار" in body


@pytest.mark.django_db
def test_event_page_has_event_schema(client):
    from django.utils import timezone

    from apps.events.models import Event

    event = Event.objects.create(
        title="نشاط للاختبار", slug="seo-event",
        start_at=timezone.now() + timezone.timedelta(days=3),
        status=Event.Status.PUBLISHED,
    )
    r = client.get(event.get_absolute_url())
    body = r.content.decode()
    assert r.status_code == 200
    assert "Event" in body
    assert "نشاط للاختبار" in body
