"""Critical paths: coupons, renewal wizard, beneficiary XOR, reminders."""
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Dependent, Profile, User
from apps.memberships.models import Coupon, Membership, MembershipRenewal, MembershipType, CouponRedemption
from apps.memberships.services import quote_price, request_renewal


def _mtype():
    return MembershipType.objects.create(name_ar="فردي", name_en="Individual", price=Decimal("1200.00"), duration_months=12)


def _user(phone="01033333301", name="عميل ديمو"):
    u = User.objects.create_user(username=phone, phone=phone, password="pw#12345", is_active=True)
    Profile.objects.create(user=u, full_name_ar=name)
    return u


@pytest.mark.django_db
class TestQuotes:
    def test_percent_coupon(self):
        t = _mtype()
        Coupon.objects.create(code="TST20", kind=Coupon.Kind.PERCENT, value=20, valid_to=date(2099, 12, 31))
        quote, err = quote_price(t, "tst20")
        assert err is None
        assert quote.discount == Decimal("240.00")
        assert quote.total == Decimal("960.00")

    def test_fixed_coupon_caps_at_price(self):
        t = _mtype()
        Coupon.objects.create(code="BIGONE", kind=Coupon.Kind.FIXED, value=5000, valid_to=date(2099, 12, 31))
        quote, err = quote_price(t, "BIGONE")
        assert err is None and quote.discount == Decimal("1200.00") and quote.total == Decimal("0.00")

    def test_expired_coupon_rejected(self):
        t = _mtype()
        Coupon.objects.create(code="OLD10", kind=Coupon.Kind.PERCENT, value=10, valid_from=date(2020, 1, 1), valid_to=date(2020, 12, 31))
        quote, err = quote_price(t, "OLD10")
        assert quote is None and err

    def test_usage_limit_enforced(self):
        t = _mtype()
        Coupon.objects.create(code="ONCE", kind=Coupon.Kind.PERCENT, value=10, valid_to=date(2099, 12, 31), usage_limit=1, used_count=1)
        quote, err = quote_price(t, "ONCE")
        assert quote is None and err


@pytest.mark.django_db
class TestRenewal:
    def test_request_renewal_creates_pending_membership_and_redemption(self):
        t = _mtype()
        user = _user()
        Coupon.objects.create(code="HALF", kind=Coupon.Kind.PERCENT, value=50, valid_to=date(2099, 12, 31))
        membership, err = request_renewal(user=user, membership_type=t, for_user=user, coupon_code="HALF")
        assert err is None
        assert membership.status == Membership.Status.PENDING
        assert membership.total_amount == Decimal("600.00")
        assert MembershipRenewal.objects.filter(membership=membership).exists()
        assert CouponRedemption.objects.filter(membership=membership, discount_amount=Decimal("600.00")).exists()
        assert Coupon.objects.get(code="HALF").used_count == 1

    def test_exactly_one_beneficiary_required(self):
        t = _mtype()
        user = _user()
        dep = Dependent.objects.create(guardian=user, full_name_ar="ابن ديمو", birth_date=date(2015, 1, 1), gender="M", relation="son")
        membership, err = request_renewal(user=user, membership_type=t, for_user=user, for_dependent=dep)
        assert membership is None and err
        membership, err = request_renewal(user=user, membership_type=t)
        assert membership is None and err

    def test_renew_for_dependent(self):
        t = _mtype()
        user = _user()
        dep = Dependent.objects.create(guardian=user, full_name_ar="ابن ديمو", birth_date=date(2015, 1, 1), gender="M", relation="son")
        membership, err = request_renewal(user=user, membership_type=t, for_dependent=dep)
        assert err is None
        assert membership.for_dependent == dep and membership.for_user is None


@pytest.mark.django_db
class TestWizardFlow:
    def test_full_wizard_creates_membership(self, client):
        t = _mtype()
        user = _user("01033333309")
        Coupon.objects.create(code="WIZ20", kind=Coupon.Kind.PERCENT, value=20, valid_to=date(2099, 12, 31))
        client.force_login(user)

        r1 = client.post(reverse("memberships:renew"), {"beneficiary": "self", "membership_type": t.pk})
        assert r1.status_code == 302

        r2 = client.post(reverse("memberships:renew_step2"), {"action": "apply_coupon", "coupon_code": "WIZ20"}, follow=True)
        assert "960,00" in r2.content.decode()  # USE_L10N ar → فاصلة عشرية

        r3 = client.post(reverse("memberships:renew_step3"), {}, follow=True)
        assert r3.status_code == 200
        membership = Membership.objects.get(member=user)
        assert membership.status == Membership.Status.PENDING
        assert membership.total_amount == Decimal("960.00")
        assert membership.reference in r3.content.decode()


@pytest.mark.django_db
class TestReminders:
    def test_reminders_find_expiring_membership(self):
        mtype = _mtype()
        user = _user("01033333310")
        today = timezone.now().date()
        Membership.objects.create(
            member=user, for_user=user, membership_type=mtype,
            start_date=today - timezone.timedelta(days=360),
            end_date=today + timezone.timedelta(days=7),
            status=Membership.Status.ACTIVE,
            base_amount=mtype.price, total_amount=mtype.price,
        )
        out = StringIO()
        call_command("send_renewal_reminders", days=7, stdout=out)
        assert "01033333310" in out.getvalue()
