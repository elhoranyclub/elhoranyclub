# -*- coding: utf-8 -*-
"""بيانات منظّمة (Schema.org / JSON-LD) — عشان جوجل يعرض بطاقة المركز والفعاليات والأخبار.

الأنواع المستخدمة:
  SportsActivityLocation — بيانات المركز (الاسم، العنوان، التليفون، مواعيد العمل)
  Article / Event / Course — تفاصيل كل محتوى
"""
from __future__ import annotations

from django.conf import settings

SCHEMA_CONTEXT = "https://schema.org"


def _abs(request, path: str) -> str:
    try:
        return request.build_absolute_uri(path)
    except Exception:
        return path


def organization_schema(site_settings, request=None) -> dict:
    """بطاقة المركز — بتظهر في جوجل بالاسم والعنوان والتليفون."""
    name = getattr(site_settings, "name_ar", "مركز شباب الحوراني")
    data = {
        "@context": SCHEMA_CONTEXT,
        "@type": ["SportsActivityLocation", "LocalBusiness", "Organization"],
        "name": name,
        "alternateName": getattr(site_settings, "name_en", "Al-Hourani Youth Sports Center"),
        "description": getattr(site_settings, "tagline_ar", "")
        or "مركز شباب الحوراني — اشتراكات وبطولات ودورات ورحلات وأنشطة رياضية.",
        "url": _abs(request, "/") if request else "",
        "telephone": getattr(site_settings, "phone", ""),
        "priceRange": "$$",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": getattr(site_settings, "address_ar", ""),
            "addressLocality": "فارسكور",
            "addressRegion": "دمياط",
            "addressCountry": "EG",
        },
        "openingHours": "Mo-Su 07:00-22:00",
        "areaServed": {"@type": "City", "name": "فارسكور"},
        "sameAs": [
            u for u in [
                getattr(site_settings, "facebook_url", ""),
                getattr(site_settings, "instagram_url", ""),
                getattr(site_settings, "youtube_url", ""),
                getattr(site_settings, "tiktok_url", ""),
            ] if u
        ],
    }
    if getattr(site_settings, "logo", None):
        try:
            data["logo"] = _abs(request, site_settings.logo.url) if request else site_settings.logo.url
        except Exception:
            pass
    if getattr(site_settings, "map_embed_url", ""):
        data["hasMap"] = site_settings.map_embed_url
    return data


def article_schema(article, request=None) -> dict:
    data = {
        "@context": SCHEMA_CONTEXT,
        "@type": "Article",
        "headline": article.title,
        "description": article.summary or (article.content or "")[:160],
        "datePublished": article.published_at.isoformat() if article.published_at else None,
        "dateModified": article.updated_at.isoformat() if article.updated_at else None,
        "author": {"@type": "Organization", "name": getattr(settings, "DEFAULT_CENTER_NAME_AR", "مركز شباب الحوراني")},
        "publisher": {"@type": "Organization", "name": getattr(settings, "DEFAULT_CENTER_NAME_AR", "مركز شباب الحوراني")},
        "inLanguage": "ar",
        "mainEntityOfPage": {"@type": "WebPage", "@id": _abs(request, article.get_absolute_url())} if request else None,
    }
    if article.cover:
        try:
            data["image"] = [_abs(request, article.cover.url)] if request else [article.cover.url]
        except Exception:
            pass
    return {k: v for k, v in data.items() if v is not None}


def event_schema(event, request=None) -> dict:
    data = {
        "@context": SCHEMA_CONTEXT,
        "@type": "Event",
        "name": event.title,
        "description": (event.description or "")[:300],
        "startDate": event.start_at.isoformat(),
        "endDate": event.end_at.isoformat() if event.end_at else None,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": event.location,
            "address": {"@type": "PostalAddress", "addressCountry": "EG"},
        },
        "organizer": {"@type": "Organization", "name": getattr(settings, "DEFAULT_CENTER_NAME_AR", "مركز شباب الحوراني")},
        "inLanguage": "ar",
        "url": _abs(request, event.get_absolute_url()) if request else "",
    }
    if event.price:
        data["offers"] = {
            "@type": "Offer",
            "price": str(event.price),
            "priceCurrency": "EGP",
            "availability": "https://schema.org/InStock",
            "url": _abs(request, event.get_absolute_url()) if request else "",
        }
    if event.image:
        try:
            data["image"] = [_abs(request, event.image.url)] if request else [event.image.url]
        except Exception:
            pass
    return {k: v for k, v in data.items() if v is not None}


def course_schema(course, request=None) -> dict:
    data = {
        "@context": SCHEMA_CONTEXT,
        "@type": "Course",
        "name": course.name,
        "description": (course.description or "")[:300],
        "provider": {"@type": "Organization", "name": getattr(settings, "DEFAULT_CENTER_NAME_AR", "مركز شباب الحوراني")},
        "inLanguage": "ar",
        "url": _abs(request, course.get_absolute_url()) if request else "",
    }
    if course.start_date:
        data["startDate"] = course.start_date.isoformat()
    if course.coach:
        data["provider"] = {
            "@type": "Organization",
            "name": course.coach.get_full_name() or getattr(settings, "DEFAULT_CENTER_NAME_AR", "مركز شباب الحوراني"),
        }
    if course.price:
        data["offers"] = {
            "@type": "Offer",
            "price": str(course.price),
            "priceCurrency": "EGP",
            "availability": "https://schema.org/InStock",
        }
    return {k: v for k, v in data.items() if v is not None}


def trip_schema(trip, request=None) -> dict:
    data = {
        "@context": SCHEMA_CONTEXT,
        "@type": "Event",
        "name": trip.name,
        "description": (trip.description or "")[:300],
        "startDate": trip.trip_date.isoformat() if trip.trip_date else None,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": trip.destination,
            "address": {"@type": "PostalAddress", "addressCountry": "EG"},
        },
        "organizer": {"@type": "Organization", "name": getattr(settings, "DEFAULT_CENTER_NAME_AR", "مركز شباب الحوراني")},
        "inLanguage": "ar",
    }
    if trip.member_price:
        data["offers"] = {
            "@type": "Offer",
            "price": str(trip.member_price),
            "priceCurrency": "EGP",
        }
    return {k: v for k, v in data.items() if v is not None}


def tournament_schema(tournament, request=None) -> dict:
    return {
        "@context": SCHEMA_CONTEXT,
        "@type": "SportsEvent",
        "name": tournament.name,
        "description": (tournament.description or "")[:300],
        "startDate": tournament.start_date.isoformat() if tournament.start_date else None,
        "endDate": tournament.end_date.isoformat() if tournament.end_date else None,
        "organizer": {"@type": "Organization", "name": getattr(settings, "DEFAULT_CENTER_NAME_AR", "مركز شباب الحوراني")},
        "inLanguage": "ar",
        "url": _abs(request, tournament.get_absolute_url()) if request else "",
    }
