"""News: only live articles are listed; sanitization strips scripts."""
import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.news.models import NewsArticle, sanitize_html
from apps.news.views import live_articles


@pytest.mark.django_db
class TestLiveArticles:
    def test_drafts_and_scheduled_hidden(self):
        NewsArticle.objects.create(title="مسودة خفية", status=NewsArticle.Status.DRAFT)
        NewsArticle.objects.create(title="مجدول للمستقبل", status=NewsArticle.Status.SCHEDULED, published_at=timezone.now() + timezone.timedelta(days=3))
        NewsArticle.objects.create(title="منشور ظاهر", status=NewsArticle.Status.PUBLISHED)
        titles = list(live_articles().values_list("title", flat=True))
        assert "مسودة خفية" not in titles
        assert "مجدول للمستقبل" not in titles
        assert "منشور ظاهر" in titles

    def test_content_sanitized_on_save(self):
        article = NewsArticle.objects.create(
            title="خبر",
            status=NewsArticle.Status.PUBLISHED,
            content='<p onclick="evil()">أهلاً</p><script>alert(1)</script><a href="javascript:bad()">لنك</a><strong>مهم</strong>',
        )
        assert "<script>" not in article.content
        assert "onclick" not in article.content
        assert "javascript:" not in article.content
        assert "<strong>مهم</strong>" in article.content


def test_sanitize_keeps_safe_html():
    assert sanitize_html("<p>مرحبا <strong>بالعالم</strong></p>") == "<p>مرحبا <strong>بالعالم</strong></p>"
