"""Critical path: event capacity, waitlist, cancellation promotion."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Profile, User
from apps.events.models import Event, EventRegistration
from apps.events.services import cancel_registration, register_for_event


def _make_user(phone, name):
    u = User.objects.create_user(username=phone, phone=phone, password="pw#12345", is_active=True)
    Profile.objects.create(user=u, full_name_ar=name)
    return u


def _event(capacity=1):
    return Event.objects.create(
        title="اختبار الحدث",
        start_at=timezone.now() + timedelta(days=30),
        capacity=capacity,
        status=Event.Status.PUBLISHED,
    )


@pytest.mark.django_db
class TestCapacity:
    def test_first_confirmed_second_waitlisted(self):
        event = _event(capacity=1)
        u1 = _make_user("01055550001", "عضو واحد")
        u2 = _make_user("01055550002", "عضو اتنين")
        r1 = register_for_event(event, u1)
        r2 = register_for_event(event, u2)
        assert r1.registration.status == EventRegistration.Status.CONFIRMED
        assert r2.registration.status == EventRegistration.Status.WAITLIST

    def test_cancel_promotes_waitlist(self):
        event = _event(capacity=1)
        u1 = _make_user("01055550003", "عضو واحد")
        u2 = _make_user("01055550004", "عضو اتنين")
        register_for_event(event, u1)
        register_for_event(event, u2)
        reg1 = EventRegistration.objects.get(event=event, user=u1)
        ok, _msg = cancel_registration(reg1, cutoff_hours=24)
        assert ok
        assert EventRegistration.objects.get(event=event, user=u2).status == EventRegistration.Status.CONFIRMED

    def test_double_registration_rejected(self):
        event = _event(capacity=2)
        u1 = _make_user("01055550005", "عضو واحد")
        assert register_for_event(event, u1).ok
        assert not register_for_event(event, u1).ok

    def test_cancel_too_late_rejected(self):
        event = Event.objects.create(
            title="قريب",
            start_at=timezone.now() + timedelta(hours=2),  # أقل من cutoff
            capacity=10,
            status=Event.Status.PUBLISHED,
        )
        u1 = _make_user("01055550006", "عضو واحد")
        register_for_event(event, u1)
        reg = EventRegistration.objects.get(event=event, user=u1)
        ok, msg = cancel_registration(reg, cutoff_hours=24)
        assert not ok
