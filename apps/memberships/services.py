"""Business logic: quotes, coupon validation, renewal requests, late fines."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import SiteSettings

from .models import Coupon, CouponRedemption, Membership, MembershipRenewal, MembershipType


def current_membership(user, *, for_user=None, for_dependent=None) -> Membership | None:
    """أحدث اشتراك لهذا الهدف بغض النظر عن حالته (للعرض)."""
    qs = Membership.objects.filter(member=user)
    if for_dependent is not None:
        qs = qs.filter(for_dependent=for_dependent)
    else:
        qs = qs.filter(for_user=for_user or user)
    return qs.select_related("membership_type").first()


def current_active(user, *, for_user=None, for_dependent=None) -> Membership | None:
    target = current_membership(user, for_user=for_user, for_dependent=for_dependent)
    if target and target.is_current:
        return target
    return None


def beneficiary_memberships(user):
    """اشتراكات المستخدم + كل التابعين، مرتبة بالأحدث."""
    return (
        Membership.objects.filter(member=user)
        .select_related("membership_type", "for_dependent")
        .order_by("-end_date", "-created_at")
    )


@dataclass
class LateFine:
    """Fine applied to members who lapse for 1+ year from the last payment."""

    due: bool
    days_since_payment: int
    percent: Decimal
    amount: Decimal
    base: Decimal  # value of the current subscription type (basis for the fine)


def late_fine(user, *, for_user=None, for_dependent=None) -> LateFine:
    """Compute the late-renewal fine for a beneficiary (self or dependent).

    Due when: the beneficiary has a past membership whose start date is 1+ year ago
    (i.e. the member did not renew within a year of paying), and the admin has set a
    fine percentage in SiteSettings (شاشة الإدارة ← الإعدادات ← نسبة غرامة التأخير).
    """
    latest = Membership.objects.filter(member=user)
    if for_dependent is not None:
        latest = latest.filter(for_dependent=for_dependent)
    else:
        latest = latest.filter(for_user=for_user or user)
    latest = latest.select_related("membership_type").order_by("-start_date", "-created_at").first()
    percent = SiteSettings.load().late_fine_percent or Decimal("0")
    today = timezone.localdate()
    if latest is None or not percent:
        return LateFine(due=False, days_since_payment=0, percent=percent, amount=Decimal("0"), base=Decimal("0"))
    days = (today - latest.start_date).days
    if days < 365:
        return LateFine(due=False, days_since_payment=days, percent=percent, amount=Decimal("0"), base=latest.membership_type.price)
    base = latest.membership_type.price
    amount = (base * percent / Decimal("100")).quantize(Decimal("0.01"))
    return LateFine(due=True, days_since_payment=days, percent=percent, amount=amount, base=base)


@dataclass
class Quote:
    base: Decimal
    discount: Decimal
    fine: Decimal
    total: Decimal
    coupon: Coupon | None


def quote_price(membership_type: MembershipType, coupon_code: str = "", *, user=None, for_user=None, for_dependent=None) -> tuple[Quote | None, str | None]:
    """احسب السعر بعد الكوبون + غرامة التأخير إن وجدت. ترجع (Quote, خطأ) — واحد منهم فقط."""
    base = membership_type.price
    discount = Decimal("0")
    coupon = None
    code = (coupon_code or "").strip().upper()
    if code:
        coupon = _validate_coupon(code, base)
        if isinstance(coupon, str):
            return None, coupon
        if coupon.kind == Coupon.Kind.PERCENT:
            discount = (base * coupon.value / Decimal("100")).quantize(Decimal("0.01"))
        else:
            discount = min(base, coupon.value)
    fine = late_fine(user, for_user=for_user, for_dependent=for_dependent).amount if user else Decimal("0")
    return Quote(base=base, discount=discount, fine=fine, total=base - discount + fine, coupon=coupon), None


def _validate_coupon(code: str, base: Decimal) -> Coupon | str:
    try:
        coupon = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        return _("كود الخصم غير صحيح.")
    today = timezone.localdate()
    if not coupon.is_active:
        return _("هذا الكوبون غير نشط.")
    if today < coupon.valid_from or today > coupon.valid_to:
        return _("انتهت صلاحية هذا الكوبون.")
    if coupon.min_amount and base < coupon.min_amount:
        return _("الحد الأدنى للفاتورة لاستخدام هذا الكوبون %(min)s ج.") % {"min": coupon.min_amount}
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return _("وصل هذا الكوبون للحد الأقصى للاستخدام.")
    return coupon


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def request_renewal(*, user, membership_type: MembershipType, for_user=None, for_dependent=None, coupon_code: str = "") -> tuple[Membership | None, str | None]:
    """ينشئ اشتراك «قيد المراجعة» بعد التحقق الذري من الكوبون."""
    if bool(for_user) == bool(for_dependent):
        return None, _("يجب تحديد المستفيد: أنت أو أحد تابعيك.")

    quote, error = quote_price(
        membership_type, coupon_code,
        user=user,
        for_user=for_user or (user if for_dependent is None else None),
        for_dependent=for_dependent,
    )
    if error:
        return None, error

    today = timezone.localdate()
    start_date, end_date = today, _add_months(today, membership_type.duration_months) - timezone.timedelta(days=1)

    with transaction.atomic():
        coupon = None
        if quote.coupon:
            coupon = Coupon.objects.select_for_update().get(pk=quote.coupon.pk)
            if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
                return None, _("وصل هذا الكوبون للحد الأقصى للاستخدام — أعد المحاولة بدون كوبون.")
            coupon.used_count += 1
            coupon.save(update_fields=["used_count"])

        membership = Membership.objects.create(
            member=user,
            for_user=for_user,
            for_dependent=for_dependent,
            membership_type=membership_type,
            start_date=start_date,
            end_date=end_date,
            status=Membership.Status.PENDING,
            base_amount=quote.base,
            discount_amount=quote.discount,
            fine_amount=quote.fine,
            total_amount=quote.total,
            coupon=coupon,
        )
        MembershipRenewal.objects.create(membership=membership, initiator=MembershipRenewal.Initiator.SELF)
        if coupon:
            CouponRedemption.objects.create(coupon=coupon, membership=membership, user=user, discount_amount=quote.discount)
    return membership, None


def activate_membership(membership: Membership, *, start: date | None = None) -> Membership:
    """يفعّل اشتراك قيد المراجعة: من اليوم + المدة المسجلة في النوع."""
    import calendar

    start = start or timezone.now().date()
    month = start.month - 1 + membership.membership_type.duration_months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    membership.start_date = start
    membership.end_date = date(year, month, day) - timezone.timedelta(days=1)
    membership.status = Membership.Status.ACTIVE
    membership.save(update_fields=["start_date", "end_date", "status", "updated_at"])
    return membership


def renewal_status_breakdown(user):
    """ملخص لكل مستفيد (أنا + تابعي): الاشتراك الحالي والعداد."""
    targets = [("self", user.get_full_name() or user.phone, getattr(user, "profile", None), current_membership(user, for_user=user))]
    for dep in user.dependents.all():
        targets.append((dep.id, dep.full_name_ar, None, current_membership(user, for_dependent=dep)))
    return targets
