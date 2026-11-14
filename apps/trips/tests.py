"""Critical paths: capacity/waitlist, guardian consent, cancel policy, pricing."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Dependent, Profile, User
from apps.trips.models import GuardianConsent, Trip, TripBooking, TripPassenger
from apps.trips.services import cancel_booking, create_booking


def _trip(capacity=40, price=250, guest=300):
    return Trip.objects.create(
        name="رحلة اختبار",
        destination="الغردقة",
        trip_date=date.today() + timedelta(days=30),
        member_price=Decimal(str(price)),
        guest_price=Decimal(str(guest)),
        capacity=capacity,
        status=Trip.Status.OPEN,
    )


def _user(phone="01066660001", name="عضو رحلة"):
    u = User.objects.create_user(username=phone, phone=phone, password="pw#12345", is_active=True)
    Profile.objects.create(user=u, full_name_ar=name, birth_date=date(1988, 1, 1), gender="M")
    return u


@pytest.mark.django_db
class TestBooking:
    def test_atomic_capacity_moves_to_waitlist(self):
        trip = _trip(capacity=1)
        u1, u2 = _user("01066660011"), _user("01066660012")
        r1, _created = None, None
        result1 = create_booking(trip=trip, booked_by=u1, passengers=[{"full_name": "A", "relation": "self", "age": 35, "is_member": True, "medical_notes": ""}])
        assert result1.ok and result1.booking.status == TripBooking.Status.PENDING
        result2 = create_booking(trip=trip, booked_by=u2, passengers=[{"full_name": "B", "relation": "self", "age": 30, "is_member": True, "medical_notes": ""}])
        assert result2.ok and result2.booking.status == TripBooking.Status.WAITLIST

    def test_minor_requires_guardian_signature(self):
        trip = _trip()
        user = _user()
        dep = Dependent.objects.create(guardian=user, full_name_ar="ابن اختبار", birth_date=date(2016, 3, 1), gender="M", relation="son")
        passengers = [
            {"full_name": user.profile.full_name_ar, "relation": "self", "age": 35, "is_member": True, "medical_notes": ""},
            {"full_name": dep.full_name_ar, "relation": "dependent", "age": 10, "is_member": True, "medical_notes": ""},
        ]
        # بدون توقيع — يجب الرفض
        result = create_booking(trip=trip, booked_by=user, passengers=passengers)
        assert not result.ok
        # بالتوقيع — تُنشأ موافقة
        result = create_booking(trip=trip, booked_by=user, passengers=passengers, signature_name="أحمد ولي الأمر")
        assert result.ok
        assert GuardianConsent.objects.filter(booking=result.booking, guardian=user).count() == 1

    def test_guest_pricing(self):
        trip = _trip(price=250, guest=300)
        user = _user()
        result = create_booking(trip=trip, booked_by=user, passengers=[
            {"full_name": "عضو", "relation": "self", "age": 30, "is_member": True, "medical_notes": ""},
            {"full_name": "ضيف", "relation": "guest", "age": 28, "is_member": False, "medical_notes": ""},
        ])
        assert result.ok
        assert result.booking.total_amount == Decimal("550")
        assert result.booking.member_count == 1 and result.booking.guest_count == 1

    def test_cancel_before_cutoff(self):
        trip = _trip()
        user = _user()
        result = create_booking(trip=trip, booked_by=user, passengers=[{"full_name": "A", "relation": "self", "age": 30, "is_member": True, "medical_notes": ""}])
        ok, _created = cancel_booking(result.booking, cutoff_hours=72)
        assert ok
        result = create_booking(trip=trip, booked_by=user, passengers=[{"full_name": "A", "relation": "self", "age": 30, "is_member": True, "medical_notes": ""}])
        # trip بعد 30 يوم — الإلغاء مسموح
        ok, _created = cancel_booking(result.booking, cutoff_hours=72)
        assert ok
