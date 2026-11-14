"""Root URL configuration — مركز شباب الحوراني"""
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

from apps.core import views as core_views
from apps.core.sitemaps import CoursesSitemap, EventsSitemap, NewsSitemap, StaticViewSitemap, TournamentsSitemap, TripsSitemap
from django.contrib.sitemaps.views import sitemap

# /admin/ للسوبر أدمن فقط — باقي الموظفين شغالين من /manage/ داخل الموقع
def _superuser_only_permission(request):
    user = getattr(request, "user", None)
    return bool(user and user.is_active and user.is_superuser)
admin.site.has_permission = _superuser_only_permission

# لوحة تحكم المركز — عنوان وشعار مخصصين بدل "Django administration"
admin.site.site_header = "مركز شباب الحوراني — لوحة التحكم"
admin.site.site_title = "مركز شباب الحوراني"
admin.site.index_title = "لوحة التحكم"

sitemaps = {
    "static": StaticViewSitemap,
    "news": NewsSitemap,
    "events": EventsSitemap,
    "tournaments": TournamentsSitemap,
    "courses": CoursesSitemap,
    "trips": TripsSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    # Language switcher (POST /i18n/setlang/)
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/", include("apps.api.urls")),
    # SEO
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    # Convenience aliases (uptime probes, PWA manifest at root)
    path("health", core_views.healthz),
    path("sw.js", core_views.sw_js, name="sw_js"),
    path("manifest.webmanifest", RedirectView.as_view(url="/static/manifest.webmanifest", permanent=True)),
]

urlpatterns += i18n_patterns(
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("memberships/", include("apps.memberships.urls")),
    path("news/", include("apps.news.urls")),
    path("events/", include("apps.events.urls")),
    path("tournaments/", include("apps.tournaments.urls")),
    path("courses/", include("apps.courses.urls")),
    path("trips/", include("apps.trips.urls")),
    path("payments/", include("apps.payments.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("gallery/", include("apps.gallery.urls")),
    path("pages/", include("apps.pages.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    prefix_default_language=False,  # Arabic (default) stays on /, English on /en/
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
elif not getattr(settings, "USE_CLOUDINARY", False):
    # إنتاج بدون Cloudinary: لازم نقدّم ملفات الـ media بنفينا (وإلا الصور المرفوعة
    # هتتحفظ بس مش هتظهر). على Render الـ disk مؤقت — فعّل CloudINARY قبل النشر النهائي.
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]

handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
handler403 = "apps.core.views.error_403"
