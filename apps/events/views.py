"""Events views — تقويم + قائمة، تسجيل/إلغاء ذري بفحص السعة."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.seo import event_schema
from .models import Event, EventRegistration
from .services import cancel_registration, register_for_event

WEEKDAYS_AR = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]


def published_events():
    return Event.objects.filter(status=Event.Status.PUBLISHED).prefetch_related("registrations")


def _parse_month(value: str | None) -> date:
    today = timezone.now().date()
    try:
        year, month = (int(p) for p in (value or "").split("-"))
        if not (1 <= month <= 12):
            raise ValueError
        return date(year, month, 1)
    except (ValueError, TypeError):
        return today.replace(day=1)


def _month_grid(month_start: date):
    """صفوف أسابيع (السبت → الجمعة) مع أحداث كل يوم."""
    cal = calendar.Calendar(firstweekday=5)  # السبت
    days = list(cal.itermonthdates(month_start.year, month_start.month))
    events = list(
        published_events().filter(
            start_at__date__gte=month_start,
            start_at__date__lt=(month_start.replace(day=28) + timedelta(days=4)).replace(day=1),
        )
    )
    by_day: dict[date, list[Event]] = {}
    for ev in events:
        by_day.setdefault(timezone.localtime(ev.start_at).date(), []).append(ev)
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    days_with_events = {d.isoformat() for d in by_day}
    return weeks, by_day, days_with_events


def event_list(request):
    view = request.GET.get("view", "list")
    month_start = _parse_month(request.GET.get("m"))
    selected_day = request.GET.get("day") or timezone.now().date().isoformat()
    try:
        selected_date = date.fromisoformat(selected_day)
    except ValueError:
        selected_date = timezone.now().date()

    now = timezone.now()
    upcoming = published_events().filter(start_at__gte=now - timedelta(hours=12))[:50]
    weeks, by_day, days_with_events = _month_grid(month_start)
    day_events = by_day.get(selected_date, []) if selected_date.month == month_start.month else list(
        published_events().filter(start_at__date=selected_date)
    )

    prev_month = (month_start.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

    return render(request, "events/list.html", {
        "view": view,
        "events": upcoming,
        "weeks": weeks,
        "by_day": by_day,
        "month_start": month_start,
        "prev_month": prev_month,
        "next_month": next_month,
        "selected_date": selected_date,
        "day_events": day_events,
        "weekdays": WEEKDAYS_AR,
        "today": timezone.now().date(),
        "days_with_events": days_with_events,
    })


def _pending_payment_for(registration):
    if registration is None or registration.status != EventRegistration.Status.PENDING:
        return None
    from apps.payments.models import Payment

    return registration.payments.filter(status=Payment.Status.PENDING).select_related().first()


def event_detail(request, slug):
    event = get_object_or_404(published_events(), slug=slug)
    my_registration = None
    if request.user.is_authenticated:
        my_registration = EventRegistration.objects.filter(event=event, user=request.user).exclude(
            status=EventRegistration.Status.CANCELLED
        ).first()

    cutoff_hours = 24
    try:
        from apps.core.models import SiteSettings

        cutoff_hours = SiteSettings.load().event_cancel_cutoff_hours
    except Exception:
        pass

    hours_before = (event.start_at - timezone.now()).total_seconds() / 3600
    can_cancel = my_registration is not None and hours_before >= cutoff_hours

    return render(request, "events/detail.html", {
        "event": event,
        "my_registration": my_registration,
        "pending_payment": _pending_payment_for(my_registration),
        "can_cancel": can_cancel,
        "cutoff_hours": cutoff_hours,
        "meta_description": (event.description or event.title)[:160],
        "event_schema": event_schema(event, request),
    })


@login_required
@require_POST
def event_register(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    # محاولة إعادة تسجيل وهو بانتظار الدفع → رجّعه للدفع بدل رسالة خطأ
    existing = EventRegistration.objects.filter(
        event=event, user=request.user, status=EventRegistration.Status.PENDING
    ).first()
    if existing:
        pending = _pending_payment_for(existing)
        if pending:
            messages.info(request, _("حجزك بانتظار الدفع — أكمل الدفع لتأكيده."))
            return redirect("payments:checkout", reference=pending.reference)

    result = register_for_event(event, request.user)
    if result.ok:
        registration = result.registration
        if registration is not None and registration.status == EventRegistration.Status.PENDING:
            from apps.payments.models import Payment
            from apps.payments.services import create_payment

            payment = create_payment(
                member=request.user,
                amount=event.price,
                kind=Payment.Kind.EVENT,
                method=Payment.Method.ONLINE,
                event_registration=registration,
                note=f"رسوم فعالية {event.title}",
            )
            messages.info(request, result.message)
            return redirect("payments:checkout", reference=payment.reference)
        messages.success(request, result.message)
    else:
        messages.error(request, result.message)
    return redirect(event.get_absolute_url())


@login_required
@require_POST
def event_cancel(request, registration_id):
    registration = get_object_or_404(EventRegistration, pk=registration_id, user=request.user)
    cutoff_hours = 24
    try:
        from apps.core.models import SiteSettings

        cutoff_hours = SiteSettings.load().event_cancel_cutoff_hours
    except Exception:
        pass
    ok, msg = cancel_registration(registration, cutoff_hours=cutoff_hours)
    getattr(messages, "success" if ok else "error")(request, msg)
    return redirect(registration.event.get_absolute_url())


@login_required
def my_registrations(request):
    registrations = (
        EventRegistration.objects.filter(user=request.user)
        .select_related("event")
        .order_by("-event__start_at")
    )
    return render(request, "events/my_registrations.html", {"registrations": registrations})
