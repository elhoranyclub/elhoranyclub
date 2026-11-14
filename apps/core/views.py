"""Core views: home, generic coming-soon placeholder, health check."""
from __future__ import annotations

import re
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
# Titles for placeholder pages (Phase 0) — replaced by real views in later phases
SECTIONS = {
    "events": _("الأنشطة والفعاليات"),
    "news": _("الأخبار"),
    "gallery": _("المعرض"),
    "tournaments": _("البطولات"),
    "courses": _("الدورات التدريبية"),
    "trips": _("الرحلات الترفيهية"),
    "renew": _("تجديد الاشتراك"),
    "login": _("تسجيل الدخول"),
    "profile": _("حسابي"),
    "my_services": _("خدماتي"),
    "about": _("من نحن"),
    "facilities": _("المرافق"),
    "pricing": _("أسعار الاشتراكات"),
    "regulation": _("لائحة المركز"),
    "faq": _("الأسئلة الشائعة"),
    "contact": _("تواصل معنا"),
    "notifications": _("الإشعارات"),
}


def home(request):
    """Landing page — hero + real featured news / upcoming events (Phase 2)."""
    from django.utils import timezone
    from django.db.models import Q

    from apps.events.models import Event
    from apps.news.models import NewsArticle

    now = timezone.now()
    live = (
        NewsArticle.objects.filter(
            Q(status=NewsArticle.Status.PUBLISHED) | Q(status=NewsArticle.Status.SCHEDULED, published_at__lte=now)
        )
        .select_related("category")
    )
    featured = list(live.filter(is_featured=True)[:4])
    if not featured:
        featured = list(live[:3])
    featured_ids = [a.pk for a in featured]
    latest_news = list(live.exclude(pk__in=featured_ids)[:3])
    upcoming_events = list(
        Event.objects.filter(status=Event.Status.PUBLISHED, start_at__gte=now - timezone.timedelta(hours=12))
        .order_by("start_at")[:3]
    )
    return render(request, "pages/home.html", {
        "featured_news": featured,
        "latest_news": latest_news,
        "upcoming_events": upcoming_events,
    })


def offline(request):
    """PWA offline fallback — served by the service worker when the network is down."""
    return render(request, "offline.html")


# ----------------------------------------------------------- فيديو الدليل

GUIDE_ROLES = ("guest", "member", "dataentry", "admin")


def _guide_video_path(role: str = "guest") -> Path | None:
    """مسار فيديو الدليل لدور معيّن — من staticfiles بعد collectstatic، أو من static في التطوير."""
    if role not in GUIDE_ROLES:
        role = "guest"
    candidates = []
    static_root = getattr(settings, "STATIC_ROOT", None)
    if static_root:
        candidates.append(Path(static_root) / "guide" / f"guide-{role}.mp4")
    candidates.append(Path(settings.BASE_DIR) / "static" / "guide" / f"guide-{role}.mp4")
    for path in candidates:
        if path.exists():
            return path
    return None


def _ranged_file_response(request, path: Path, content_type: str):
    """يقدّم الملف مع دعم HTTP Range — عشان التنقّل داخل الفيديو ( scrubbing) يشتغل."""
    size = path.stat().st_size
    range_header = request.headers.get("Range", "")
    match = re.match(r"bytes=(\d*)-(\d*)", range_header or "")

    if not match:
        response = FileResponse(open(path, "rb"), content_type=content_type)
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(size)
        return response

    start = int(match.group(1)) if match.group(1) else 0
    end = int(match.group(2)) if match.group(2) else size - 1
    start = max(start, 0)
    end = min(end, size - 1)
    if start > end:
        return HttpResponse(status=416)

    length = end - start + 1

    def stream():
        with open(path, "rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    response = StreamingHttpResponse(stream(), status=206, content_type=content_type)
    response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Content-Length"] = str(length)
    response["Accept-Ranges"] = "bytes"
    return response


def guide_video(request, role: str = "guest"):
    """فيديو «اعرف الموقع أكتر» لدور معيّن — مع دعم Range عشان تشغيل الفيديو والتنقّل فيه."""
    path = _guide_video_path(role)
    if path is None:
        raise Http404("فيديو الدليل غير موجود")
    return _ranged_file_response(request, path, "video/mp4")


def sw_js(request):
    """Serve sw.js from the site root so the PWA scope is '/' (not /static/)."""
    from django.conf import settings
    from django.http import FileResponse

    response = FileResponse(open(settings.BASE_DIR / "static" / "sw.js", "rb"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def robots_txt(request):
    """robots.txt — يشير لخريطة الموقع، ويحجب لوحات التحكم والـ API الإداري."""
    from django.http import HttpResponse

    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /accounts/",
        "Disallow: /api/",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def coming_soon(request, section: str):
    """Branded placeholder for sections arriving in later phases."""
    title = SECTIONS.get(section, _("قيد التطوير"))
    return render(request, "pages/coming_soon.html", {"section_title": title})


def placeholder(section: str):
    """Build a view callable bound to a section — used in app urls.py files."""

    @wraps(coming_soon)
    def view(request):
        return coming_soon(request, section)

    return view


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)


def error_403(request, exception=None):
    return forbidden(request)


def forbidden(request):
    """Friendly 403 page — used instead of bare HttpResponse(status=403)."""
    return render(request, "errors/403.html", status=403)


def healthz(request):
    """Lightweight liveness probe for load balancers / uptime checks."""
    return JsonResponse({"status": "ok"})
