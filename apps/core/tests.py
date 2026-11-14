"""Phase 9: sitemap, robots, offline, PWA files."""
from pathlib import Path

import pytest

from apps.news.models import NewsArticle, NewsCategory

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@pytest.mark.django_db
class TestSEO:
    def test_sitemap_xml(self, client):
        cat = NewsCategory.objects.create(name_ar="إعلانات", slug="announce")
        NewsArticle.objects.create(title="خبر تجريبي", category=cat, status=NewsArticle.Status.PUBLISHED)
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        assert "<urlset" in response.content.decode() or "<sitemapindex" in response.content.decode()

    def test_robots_txt(self, client):
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert "Sitemap:" in response.content.decode()
        assert "Disallow: /admin/" in response.content.decode()

    def test_offline_page(self, client):
        response = client.get("/offline/")
        assert response.status_code == 200

    def test_sw_and_manifest_exist_and_valid(self):
        sw = BASE_DIR / "static" / "sw.js"
        manifest = BASE_DIR / "static" / "manifest.webmanifest"
        assert sw.exists() and "addEventListener('install'" in sw.read_text(encoding="utf-8")
        assert manifest.exists()
        import json

        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["name"] and data["start_url"] == "/"
        assert data["display"] == "standalone"


@pytest.mark.django_db
class TestGuideVideo:
    def test_video_served_with_range_support(self, client):
        """فيديو الدليل — لازم يردود على Range عشان التنقّل داخل الفيديو يشتغل."""
        response = client.get("/guide/video/guest/", headers={"Range": "bytes=0-99"})
        assert response.status_code == 206
        assert response["Content-Type"] == "video/mp4"
        assert response["Accept-Ranges"] == "bytes"
        assert response["Content-Range"].startswith("bytes 0-99/")
        assert len(b"".join(response.streaming_content)) == 100

    def test_video_full_request(self, client):
        response = client.get("/guide/video/member/")
        assert response.status_code == 200
        assert response["Accept-Ranges"] == "bytes"

    def test_every_role_has_a_video(self, client):
        for role in ("guest", "member", "dataentry", "admin"):
            response = client.get(f"/guide/video/{role}/", headers={"Range": "bytes=0-9"})
            assert response.status_code == 206, role
