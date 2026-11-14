"""Ledger import, sequential membership numbering, late-renewal fine."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import MemberRegistry, Profile, User, allocate_membership_number
from apps.core.models import SiteSettings
from apps.memberships.models import Membership, MembershipType
from apps.memberships.services import late_fine, quote_price


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="ledgertest", phone="01055554444", password="pw-test-123", is_active=True)
    return u


@pytest.mark.django_db
def test_allocate_continues_after_ledger(user):
    p1 = Profile.objects.create(user=user, full_name_ar="واحد")
    first = int(p1.membership_number)
    MemberRegistry.objects.create(full_name_ar="عضو دفتر", national_id="11111111111111", membership_number=str(first + 100))
    nxt = int(allocate_membership_number())
    assert nxt == first + 101


@pytest.mark.django_db
def test_ledger_uniqueness_and_ordering():
    MemberRegistry.objects.create(full_name_ar="أ", national_id="22222222222222", membership_number="200")
    with pytest.raises(Exception):
        MemberRegistry.objects.create(full_name_ar="ب", national_id="33333333333333", membership_number="200")


@pytest.mark.django_db
class TestLateFine:
    def _membership(self, user, *, days_ago: int, price: Decimal = Decimal("25")):
        mtype = MembershipType.objects.create(name_ar="سنوي", price=price, duration_months=12, is_active=True)
        start = timezone.localdate() - datetime.timedelta(days=days_ago)
        return Membership.objects.create(
            member=user, for_user=user, membership_type=mtype,
            start_date=start, end_date=start + datetime.timedelta(days=364),
            status=Membership.Status.ACTIVE,
            base_amount=price, total_amount=price,
        )

    def _set_percent(self, pct: str):
        ss = SiteSettings.load()
        ss.late_fine_percent = Decimal(pct)
        ss.save(update_fields=["late_fine_percent", "updated_at"])

    def test_no_fine_before_one_year(self, user):
        self._set_percent("20")
        self._membership(user, days_ago=100)
        result = late_fine(user, for_user=user)
        assert not result.due and result.amount == Decimal("0.00")

    def test_fine_after_one_year(self, user):
        self._set_percent("20")
        self._membership(user, days_ago=400)
        result = late_fine(user, for_user=user)
        assert result.due and result.amount == Decimal("5.00")

    def test_fine_zero_percent_disables(self, user):
        self._set_percent("0")
        self._membership(user, days_ago=800)
        result = late_fine(user, for_user=user)
        assert not result.due

    def test_no_memberships_never_fined(self, user):
        self._set_percent("50")
        assert not late_fine(user, for_user=user).due


@pytest.mark.django_db
class TestQuoteWithFine:
    def test_quote_includes_fine(self, user):
        mtype = MembershipType.objects.create(name_ar="سنوي", price=Decimal("25"), duration_months=12, is_active=True)
        start = timezone.localdate() - datetime.timedelta(days=400)
        Membership.objects.create(
            member=user, for_user=user, membership_type=mtype,
            start_date=start, end_date=start + datetime.timedelta(days=364),
            status=Membership.Status.EXPIRED, base_amount=Decimal("25"), total_amount=Decimal("25"),
        )
        ss = SiteSettings.load()
        ss.late_fine_percent = Decimal("20")
        ss.save(update_fields=["late_fine_percent", "updated_at"])
        quote, err = quote_price(mtype, "", user=user, for_user=user)
        assert err is None
        assert quote.fine == Decimal("5.00")
        assert quote.total == Decimal("30.00")


@pytest.mark.django_db
def test_import_members_command(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from django.core.management import call_command

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["الاسم", "الرقم القومي", "رقم العضوية", "جمعية عمومية", "المنصب", "مدفوع حتى", "المبلغ"])
    ws.append(["استيراد تجريبي", "33311122200099", "3001", "نعم", "عضو", "2027-05-01", "25"])
    path = tmp_path / "ledger.xlsx"
    wb.save(path)

    call_command("import_members", str(path), commit=False)  # dry-run: no rows written
    assert not MemberRegistry.objects.filter(membership_number="3001").exists()

    call_command("import_members", str(path), commit=True)
    entry = MemberRegistry.objects.get(membership_number="3001")
    assert entry.full_name_ar == "استيراد تجريبي"
    assert entry.is_general_assembly is True
    assert entry.assembly_position == "عضو"
    assert str(entry.paid_until) == "2027-05-01"
    assert entry.last_payment_amount == Decimal("25")
