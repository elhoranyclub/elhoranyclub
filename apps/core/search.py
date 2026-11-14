"""Global search — بحث موحد عبر الأخبار والأنشطة والبطولات والدورات والرحلات والاشتراكات."""
from __future__ import annotations

from django.db.models import Q
from django.shortcuts import render


def search(request):
    query = (request.GET.get("q") or "").strip()
    groups = []

    if len(query) >= 2:
        q = query
        from apps.courses.models import Course
        from apps.events.models import Event
        from apps.memberships.models import MembershipType
        from apps.news.models import NewsArticle
        from apps.tournaments.models import Tournament
        from apps.trips.models import Trip

        news = NewsArticle.objects.filter(
            Q(status=NewsArticle.Status.PUBLISHED) & (Q(title__icontains=q) | Q(summary__icontains=q) | Q(content__icontains=q))
        ).order_by("-published_at")[:8]
        if news:
            groups.append(("الأخبار", [{"title": a.title, "url": a.get_absolute_url(), "meta": a.category.name_ar if a.category else "news"} for a in news]))

        events = Event.objects.filter(status=Event.Status.PUBLISHED).filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(location__icontains=q)).order_by("start_at")[:8]
        if events:
            groups.append(("الأنشطة والفعاليات", [{"title": e.title, "url": e.get_absolute_url(), "meta": e.start_at.strftime("%Y-%m-%d")} for e in events]))

        tournaments = Tournament.objects.exclude(status=Tournament.Status.DRAFT).filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(sport__name_ar__icontains=q))[:8]
        if tournaments:
            groups.append(("البطولات", [{"title": t.name, "url": t.get_absolute_url(), "meta": t.sport.name_ar} for t in tournaments]))

        courses = Course.objects.exclude(status=Course.Status.DRAFT).filter(Q(name__icontains=q) | Q(description__icontains=q))[:8]
        if courses:
            groups.append(("الدورات", [{"title": c.name, "url": c.get_absolute_url(), "meta": c.get_level_display()} for c in courses]))

        trips = Trip.objects.exclude(status=Trip.Status.DRAFT).filter(Q(name__icontains=q) | Q(destination__icontains=q) | Q(description__icontains=q)).order_by("trip_date")[:8]
        if trips:
            groups.append(("الرحلات", [{"title": t.name, "url": t.get_absolute_url(), "meta": t.trip_date.strftime("%Y-%m-%d")} for t in trips]))

        plans = MembershipType.objects.filter(is_active=True).filter(Q(name_ar__icontains=q) | Q(description__icontains=q))[:5]
        if plans:
            groups.append(("خطط الاشتراك", [{"title": p.name_ar, "url": "/memberships/renew/", "meta": f"{p.price} ج / سنة"} for p in plans]))

    return render(request, "pages/search.html", {"query": query, "groups": groups, "total": sum(len(g[1]) for g in groups)})
