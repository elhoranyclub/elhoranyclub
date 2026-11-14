"""
Dashboard — لوحة تحكم الموظفين (staff-only).
إحصائيات + طوابير المراجعة + تصدير CSV للعضوية والمدفوعات.
"""
from __future__ import annotations

import csv
import io
from datetime import timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import MemberRegistry, Profile, User
from apps.core.audit import AuditLog
from apps.core.manage import grouped_manageable_for
from apps.courses.models import CourseEnrollment
from apps.events.models import Event, EventRegistration
from apps.memberships.models import Membership
from apps.news.models import NewsArticle
from apps.pages.models import ContactMessage
from apps.payments.models import Payment, PaymentProof
from apps.tournaments.models import TournamentRegistration
from apps.trips.models import TripBooking


def _staff_required(user) -> bool:
    return user.is_authenticated and user.is_staff


def _month_bounds():
    now = timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def _late_fines_count():
    """Distinct members with self memberships whose latest start is 365+ days ago (others' are not fined)."""
    from django.core.cache import cache
    from django.db.models import Max

    cached = cache.get("late_fines_count")
    if cached is not None:
        return cached
    threshold = timezone.localdate() - timedelta(days=365)
    count = (
        Membership.objects.filter(for_user__isnull=False)
        .values("member")
        .annotate(latest_start=Max("start_date"))
        .filter(latest_start__lte=threshold)
        .count()
    )
    cache.set("late_fines_count", count, 600)
    return count


@user_passes_test(_staff_required, login_url="accounts:login")
def home(request: HttpRequest) -> HttpResponse:
    now = timezone.now()
    today = now.date()
    month_start, _created = _month_bounds()

    paid_month = Payment.objects.filter(status=Payment.Status.PAID, paid_at__gte=month_start)
    revenue_month = paid_month.aggregate(total=Sum("amount"))["total"] or 0
    revenue_by_kind = (
        paid_month.values("kind")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    kind_max = max([row["total"] for row in revenue_by_kind], default=1)
    kind_labels = dict(Payment.Kind.choices)

    active_memberships = Membership.objects.filter(status=Membership.Status.ACTIVE, start_date__lte=today, end_date__gte=today).count()
    expiring_soon = Membership.objects.filter(
        status=Membership.Status.ACTIVE,
        end_date__lte=today + timedelta(days=30),
        end_date__gte=today,
    ).count()
    pending_memberships = Membership.objects.filter(status=Membership.Status.PENDING).count()

    queues = {
        "payments_pending": Payment.objects.filter(status=Payment.Status.PENDING).count(),
        "proofs_pending": PaymentProof.objects.filter(status=PaymentProof.Status.PENDING).count(),
        "tournament_regs": TournamentRegistration.objects.filter(status=TournamentRegistration.Status.PENDING).count(),
        "messages": ContactMessage.objects.filter(is_read=False).count(),
        "membership_pending": pending_memberships,
        "event_waitlists": EventRegistration.objects.filter(status=EventRegistration.Status.WAITLIST).count(),
        "trip_waitlists": TripBooking.objects.filter(status=TripBooking.Status.WAITLIST).count(),
        "course_pendings": CourseEnrollment.objects.filter(status=CourseEnrollment.Status.PENDING).count(),
        "late_fines": _late_fines_count(),
        "unlinked_registry": MemberRegistry.objects.filter(linked_profile__isnull=True).count(),
    }
    queue_total = sum(queues.values())

    recent_payments = (
        Payment.objects.filter(status=Payment.Status.PAID)
        .select_related("member", "membership", "tournament_registration", "course_enrollment", "trip_booking")
        .order_by("-paid_at")[:8]
    )
    audit_entries = AuditLog.objects.select_related("actor").order_by("-created_at")[:8]
    events_today = Event.objects.filter(status=Event.Status.PUBLISHED, start_at__date=today).count()
    upcoming_events = Event.objects.filter(status=Event.Status.PUBLISHED, start_at__gte=now).order_by("start_at")[:3]
    articles_month = NewsArticle.objects.filter(status=NewsArticle.Status.PUBLISHED, published_at__gte=month_start).count()

    stats = [
        {"label": "اشتراكات نشطة", "value": active_memberships, "hint": "إجمالي الاشتراكات السارية", "tone": "green"},
        {"label": "تنتهي خلال 30 يوم", "value": expiring_soon, "hint": "مرشحة للتذكير والتجديد", "tone": "gold"},
        {"label": "إيرادات الشهر", "value": f"{revenue_month:.0f} ج", "hint": f"{paid_month.count()} عملية دفع", "tone": "navy"},
        {"label": "في طوابير المراجعة", "value": queue_total, "hint": "مدفوعات + إيصالات + تسجيلات + رسائل", "tone": "red" if queue_total else "green"},
        {"label": "فعاليات النهاردة", "value": events_today, "hint": "في جدول المركز اليوم", "tone": "navy"},
        {"label": "أخبار هذا الشهر", "value": articles_month, "hint": "مقال منشور", "tone": "green"},
    ]

    context = {
        "manage_groups": grouped_manageable_for(request.user),
        "stats": stats,
        "queues": queues,
        "revenue_by_kind": [
            {"label": kind_labels.get(row["kind"], row["kind"]), "total": row["total"], "count": row["count"], "percent": int(row["total"] * 100 / kind_max)}
            for row in revenue_by_kind
        ],
        "recent_payments": recent_payments,
        "audit_entries": audit_entries,
        "upcoming_events": upcoming_events,
    }
    return render(request, "dashboard/home.html", context)


def _csv_response(filename: str, rows):
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@user_passes_test(_staff_required, login_url="accounts:login")
def export_members_csv(request: HttpRequest) -> HttpResponse:
    rows = [["membership_number", "name_ar", "phone", "national_id", "general_assembly", "assembly_position", "governorate", "joined_at", "gender"]]
    for profile in Profile.objects.select_related("user").iterator():
        rows.append([
            profile.membership_number, profile.full_name_ar, profile.user.phone or "",
            profile.national_id,
            "yes" if profile.is_general_assembly else "no", profile.assembly_position,
            profile.governorate, profile.joined_at.isoformat(), profile.gender,
        ])
    return _csv_response("members.csv", rows)


@user_passes_test(_staff_required, login_url="accounts:login")
def export_payments_csv(request: HttpRequest) -> HttpResponse:
    rows = [["reference", "date", "member", "phone", "kind", "method", "amount", "status"]]
    for payment in Payment.objects.select_related("member").iterator():
        rows.append([
            payment.reference,
            (payment.paid_at or payment.created_at).strftime("%Y-%m-%d %H:%M"),
            payment.member.get_full_name() or "", payment.member.phone or "",
            payment.get_kind_display(), payment.get_method_display(),
            str(payment.amount), payment.get_status_display(),
        ])
    return _csv_response("payments.csv", rows)
