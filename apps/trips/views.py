"""Trips views — القائمة، التفاصيل، الحجز، قوائم الركاب (staff)، الحضور."""
from __future__ import annotations

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.seo import trip_schema
from apps.accounts.models import Dependent

from .models import GuardianConsent, Trip, TripBooking, TripPassenger
from .services import cancel_booking, create_booking, roster


def _staff_required(user):
    return user.is_authenticated and user.is_staff


def trip_list(request: HttpRequest) -> HttpResponse:
    tab = request.GET.get("tab", "open")
    base = Trip.objects.all()
    tabs = {
        "open": base.filter(status__in=[Trip.Status.OPEN, Trip.Status.FULL]),
        "completed": base.filter(status=Trip.Status.COMPLETED),
    }
    trips = tabs.get(tab, tabs["open"])
    return render(request, "trips/list.html", {"trips": trips, "tab": tab})


def trip_detail(request: HttpRequest, slug: str) -> HttpResponse:
    trip = get_object_or_404(Trip, slug=slug)
    my_booking = None
    if request.user.is_authenticated:
        my_booking = TripBooking.objects.filter(trip=trip, booked_by=request.user).exclude(status=TripBooking.Status.CANCELLED).first()
    return render(request, "trips/detail.html", {
        "trip": trip,
        "my_booking": my_booking,
        "meta_description": (trip.description or f"{trip.name} — {trip.destination}")[:160],
        "trip_schema": trip_schema(trip, request),
    })


@login_required
def book_view(request: HttpRequest, slug: str) -> HttpResponse:
    trip = get_object_or_404(Trip, slug=slug)
    if not trip.is_open:
        messages.error(request, _("باب الحجز مغلق لهذه الرحلة."))
        return redirect(trip.get_absolute_url())

    profile = getattr(request.user, "profile", None)
    targets = [("self", (profile.full_name_ar if profile else request.user.get_full_name()), True, profile.age if profile else None)]
    for dep in request.user.dependents.all():
        targets.append((f"dep:{dep.pk}", dep.full_name_ar, True, dep.age))

    if request.method == "POST":
        passengers = []
        self_checked = request.POST.get("include_self") == "on"
        if self_checked:
            passengers.append({
                "full_name": (profile.full_name_ar if profile else request.user.get_full_name()),
                "relation": TripPassenger.Relation.SELF,
                "age": profile.age if profile else None,
                "is_member": True,
                "medical_notes": "",
            })
        for dep_id in request.POST.getlist("dependents"):
            dep = get_object_or_404(Dependent, pk=dep_id, guardian=request.user)
            passengers.append({
                "full_name": dep.full_name_ar,
                "relation": TripPassenger.Relation.DEPENDENT,
                "age": dep.age,
                "is_member": True,
                "medical_notes": "",
            })
        for i in range(1, 4):
            name = (request.POST.get(f"guest_{i}") or "").strip()
            if name:
                age_str = request.POST.get(f"guest_age_{i}") or ""
                try:
                    age = int(age_str) if age_str else None
                except ValueError:
                    age = None
                passengers.append({
                    "full_name": name,
                    "relation": TripPassenger.Relation.GUEST,
                    "age": age,
                    "is_member": False,
                    "medical_notes": "",
                })

        signature = (request.POST.get("signature_name") or "").strip()
        ip = request.META.get("REMOTE_ADDR", "")
        note = (request.POST.get("note") or "").strip()[:500]

        result = create_booking(trip=trip, booked_by=request.user, passengers=passengers, note=note, signature_name=signature, ip_address=ip)
        if not result.ok:
            messages.error(request, result.message)
            return redirect("trips:book", slug=slug)

        booking = result.booking
        if booking.total_amount > 0:
            from apps.payments.models import Payment
            from apps.payments.services import create_payment

            payment = create_payment(
                member=request.user,
                amount=booking.total_amount,
                kind=Payment.Kind.TRIP,
                method=Payment.Method.ONLINE,
                trip_booking=booking,
                note=f"حجز {trip.name}",
            )
            messages.info(request, _("أكمل الدفع خلال 48 ساعة لتأكيد الحجز."))
            return redirect("payments:checkout", reference=payment.reference)

        booking.status = TripBooking.Status.CONFIRMED
        booking.save(update_fields=["status", "updated_at"])
        messages.success(request, _("تم تأكيد حجزك! نتمنى لك رحلة ممتعة."))
        return redirect("trips:my_bookings")

    return render(request, "trips/book.html", {
        "trip": trip,
        "targets": targets,
        "dependents": request.user.dependents.all(),
        "consent_text": GuardianConsent.CONSENT_TEXT,
    })


@login_required
def my_bookings(request: HttpRequest) -> HttpResponse:
    bookings = TripBooking.objects.filter(booked_by=request.user).select_related("trip").prefetch_related("passengers").order_by("-created_at")
    return render(request, "trips/my_bookings.html", {"bookings": bookings})


@login_required
@require_POST
def cancel_my_booking(request: HttpRequest, booking_id: int) -> HttpResponse:
    booking = get_object_or_404(TripBooking, pk=booking_id, booked_by=request.user)
    ok, msg = cancel_booking(booking, cutoff_hours=72)
    getattr(messages, "success" if ok else "error")(request, msg)
    return redirect("trips:my_bookings")


@user_passes_test(_staff_required, login_url="accounts:login")
def roster_view(request: HttpRequest, slug: str) -> HttpResponse:
    trip = get_object_or_404(Trip, slug=slug)
    passengers = list(roster(trip))
    bookings = TripBooking.objects.filter(trip=trip).exclude(status=TripBooking.Status.CANCELLED).select_related("booked_by").order_by("created_at")
    return render(request, "trips/roster.html", {"trip": trip, "passengers": passengers, "bookings": bookings})


@user_passes_test(_staff_required, login_url="accounts:login")
def roster_csv(request: HttpRequest, slug: str) -> HttpResponse:
    trip = get_object_or_404(Trip, slug=slug)
    passengers = roster(trip)
    response = StreamingHttpResponse((line for line in _csv_lines(trip, passengers)), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="roster-{trip.trip_date}.csv"'
    return response


def _csv_lines(trip, passengers):
    import io

    buf = io.StringIO()
    buf.write("\ufeff")  # BOM لـ Excel
    writer = csv.writer(buf)
    writer.writerow(["Trip", trip.name, str(trip.trip_date)])
    writer.writerow(["#", "الاسم", "الصلة", "السن", "الحاجز", "رقم الحجز", "ملاحظات صحية"])
    yield buf.getvalue()
    i = 1
    for p in passengers:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([i, p.full_name, p.get_relation_display(), p.age or "", p.booking.booked_by.get_full_name() or p.booking.booked_by.phone, p.booking.reference, p.medical_notes])
        i += 1
        yield buf.getvalue()


@user_passes_test(_staff_required, login_url="accounts:login")
def attendance_view(request: HttpRequest, slug: str) -> HttpResponse:
    trip = get_object_or_404(Trip, slug=slug)
    passengers = list(roster(trip))
    if request.method == "POST":
        present_count = 0
        for p in passengers:
            present = request.POST.get(f"present_{p.pk}") == "on"
            p.present = present
            p.save(update_fields=["present", "updated_at"])
            present_count += int(present)
        messages.success(request, _("تم حفظ الحضور (%(n)s راكب).") % {"n": present_count})
        return redirect("trips:attendance", slug=slug)
    return render(request, "trips/attendance.html", {"trip": trip, "passengers": passengers})
