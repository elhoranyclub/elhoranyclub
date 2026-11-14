"""Booking logic — atomic seat reservation, totals, guardian consent records."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils.translation import gettext as _

from .models import GuardianConsent, Trip, TripBooking, TripPassenger


@dataclass
class BookingResult:
    ok: bool
    message: str
    booking: TripBooking | None = None


def price_passenger(trip: Trip, is_member: bool) -> Decimal:
    return trip.member_price if is_member else trip.guest_price


def create_booking(*, trip: Trip, booked_by, passengers: list[dict], note: str = "", signature_name: str = "", ip_address: str = "") -> BookingResult:
    """
    passengers: [{full_name, relation, age, is_member, medical_notes, dependent?}]
    ينشئ الحجز ذريًا — المقاعد المُحجوزة (confirmed+pending) تُحسب على السعة.
    """
    if trip.status != Trip.Status.OPEN:
        return BookingResult(False, _("باب الحجز مغلق لهذه الرحلة."))
    if not passengers:
        return BookingResult(False, _("اختار ركابً على الأقل."))

    member_pax = sum(1 for p in passengers if p["is_member"])
    guest_pax = len(passengers) - member_pax
    total = sum((price_passenger(trip, p["is_member"]) for p in passengers), Decimal("0"))

    # التحقق من موافقة ولي الأمر: أي راكب قاصر (<18) يحتاج signature
    has_minor = any((p.get("age") is not None and p["age"] < 18) for p in passengers)
    has_consent = bool(signature_name.strip())
    if has_minor and not has_consent:
        return BookingResult(False, _("يلزم توقيع ولي الأمر لأي راكب أقل من 18 سنة."))

    with transaction.atomic():
        locked = Trip.objects.select_for_update().get(pk=trip.pk)
        seats_taken = locked.bookings.filter(
            status__in=[TripBooking.Status.CONFIRMED, TripBooking.Status.PENDING]
        ).aggregate(total=Sum("passengers_count"))["total"] or 0
        if seats_taken + len(passengers) > locked.capacity:
            booking_status = TripBooking.Status.WAITLIST
        else:
            booking_status = TripBooking.Status.PENDING

        booking = TripBooking.objects.create(
            trip=locked,
            booked_by=booked_by,
            passengers_count=len(passengers),
            member_count=member_pax,
            guest_count=guest_pax,
            total_amount=total,
            note=note[:500],
            status=booking_status,
        )
        for p in passengers:
            passenger = TripPassenger.objects.create(
                booking=booking,
                relation=p["relation"],
                full_name=p["full_name"][:150],
                age=p.get("age"),
                medical_notes=(p.get("medical_notes") or "")[:255],
            )
            if has_minor and p.get("age") is not None and p["age"] < 18 and signature_name.strip():
                GuardianConsent.objects.create(
                    passenger=passenger,
                    booking=booking,
                    guardian=booked_by,
                    signature_name=signature_name.strip()[:150],
                    consent_text=GuardianConsent.CONSENT_TEXT,
                    ip_address=ip_address or None,
                )
    return BookingResult(True, _("تم حجز مقاعدك — أكمل الدفع لتأكيد الحجز."), booking)


def cancel_booking(booking: TripBooking, *, cutoff_hours: int = 72) -> tuple[bool, str]:
    from django.utils import timezone as tz

    trip_dt = tz.make_aware(tz.datetime.combine(booking.trip.trip_date, tz.datetime.min.time()))
    hours_before = (trip_dt - tz.now()).total_seconds() / 3600
    if hours_before < cutoff_hours:
        return False, _("فات موعد الإلغاء المجاني (%(h)s ساعة قبل التحرك) — اتصل بالاستقبال.") % {"h": cutoff_hours}
    booking.status = TripBooking.Status.CANCELLED
    booking.save(update_fields=["status", "updated_at"])
    return True, _("تم إلغاء حجزك.")


def roster(trip: Trip):
    return (
        TripPassenger.objects.filter(booking__trip=trip, booking__status__in=[TripBooking.Status.CONFIRMED, TripBooking.Status.PENDING])
        .select_related("booking", "booking__booked_by")
        .order_by("booking__created_at", "id")
    )
