"""News views — list (search + category filter + pagination) and detail."""
from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.seo import article_schema
from .models import NewsArticle, NewsCategory


def live_articles():
    now = timezone.now()
    return (
        NewsArticle.objects.filter(
            Q(status=NewsArticle.Status.PUBLISHED) | Q(status=NewsArticle.Status.SCHEDULED, published_at__lte=now)
        )
        .select_related("category", "author")
        .prefetch_related("tags")
    )


def article_list(request):
    qs = live_articles()
    category = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()

    if category:
        qs = qs.filter(category__slug=category)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(summary__icontains=query) | Q(content__icontains=query))

    paginator = Paginator(qs, 9)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "news/list.html", {
        "page": page,
        "categories": NewsCategory.objects.all(),
        "current_category": category,
        "query": query,
    })


def article_detail(request, slug):
    article = get_object_or_404(live_articles().prefetch_related("images"), slug=slug)
    related = live_articles().filter(category=article.category).exclude(pk=article.pk)[:3] if article.category else []
    return render(request, "news/detail.html", {
        "article": article,
        "related": related,
        "meta_description": article.summary or article.title,
        "article_schema": article_schema(article, request),
    })
