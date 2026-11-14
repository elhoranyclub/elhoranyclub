"""Critical paths: enrollment rules, capacity/waitlist, completion + certificate."""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Dependent, Profile, User
from apps.courses.models import Attendance, Certificate, Course, CourseEnrollment
from apps.courses.services import complete_enrollment, enroll
from apps.payments.models import Payment
from apps.payments.services import confirm_payment, create_payment
from apps.tournaments.models import Sport


def _user(phone="01088880001", name="عضو دورة", age=None):
    u = User.objects.create_user(username=phone, phone=phone, password="pw#12345", is_active=True)
    Profile.objects.create(user=u, full_name_ar=name, birth_date=date(2014, 1, 15), gender="M")
    return u


def _course(**kwargs):
    sport = Sport.objects.create(name_ar="كاراتيه", is_team_sport=False)
    defaults = {"name": "كاراتيه تجريبي", "sport": sport, "status": Course.Status.OPEN, "price": Decimal("0"), "capacity": 2, "age_min": 4, "age_max": 99}
    defaults.update(kwargs)
    return Course.objects.create(**defaults)


@pytest.mark.django_db
class TestEnrollmentRules:
    def test_waitlist_when_full(self):
        course = _course(capacity=1)
        u1, u2 = _user("01088880011"), _user("01088880012")
        e1, err1 = enroll(user=u1, course=course, for_user=True)
        assert err1 is None and e1.status == CourseEnrollment.Status.CONFIRMED
        e2, err2 = enroll(user=u2, course=course, for_user=True)
        assert err2 is None and e2.status == CourseEnrollment.Status.WAITLIST

    def test_age_out_of_range_rejected(self):
        course = _course(age_min=4, age_max=12)
        old = _user("01088880013")
        old.profile.birth_date = date(1980, 1, 1)
        old.profile.save()
        enrollment, err = enroll(user=old, course=course, for_user=True)
        assert enrollment is None and err

    def test_medical_acknowledgement_required(self):
        course = _course(requires_medical=True)
        user = _user("01088880014")
        enrollment, err = enroll(user=user, course=course, for_user=True, health_acknowledged=False)
        assert enrollment is None and err
        enrollment, err = enroll(user=user, course=course, for_user=True, health_acknowledged=True)
        assert err is None

    def test_duplicate_enrollment_rejected(self):
        course = _course()
        user = _user("01088880015")
        enroll(user=user, course=course, for_user=True)
        enrollment, err = enroll(user=user, course=course, for_user=True)
        assert enrollment is None and err


@pytest.mark.django_db
class TestPaidEnrollment:
    def test_paid_enrollment_starts_pending_and_confirms_on_payment(self):
        course = _course(price=Decimal("100"), price_type=Course.PriceType.MONTHLY)
        user = _user("01088880016")
        enrollment, err = enroll(user=user, course=course, for_user=True)
        assert err is None and enrollment.status == CourseEnrollment.Status.PENDING

        payment = create_payment(member=user, amount=Decimal("100"), kind="course", method="cash", course_enrollment=enrollment)
        confirm_payment(payment)
        enrollment.refresh_from_db()
        assert enrollment.status == CourseEnrollment.Status.CONFIRMED


@pytest.mark.django_db
class TestCompletionAndCertificate:
    def test_complete_issues_certificate(self):
        course = _course()
        user = _user("01088880017")
        enrollment, _created = enroll(user=user, course=course, for_user=True)
        certificate = complete_enrollment(enrollment)
        assert certificate.number.startswith("CERT-")
        enrollment.refresh_from_db()
        assert enrollment.status == CourseEnrollment.Status.COMPLETED
        assert Certificate.objects.filter(enrollment=enrollment).exists()
