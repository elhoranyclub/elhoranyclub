"""Ledger (الدفتر) management screens for staff.

- registry_list: all imported rows + search + GA filter + CSV export.
- registry_link: link an auto-registered profile to its paper-ledger row
  (copies membership number, national ID, GA flag/position, and creates the
  paid subscription period when the ledger says it's paid).
- registry_unlink: undo a mistaken link (profile keeps its own membership number;
  ledger row becomes unlinked again).
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.audit import record

from .models import MemberRegistry, Profile, User
from apps.memberships.models import Membership, MembershipType


def _staff(user) -> bool:
    return user.is_authenticated and user.is_staff


def _csv_response(filename: str, rows):
    import io

    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@user_passes_test(_staff, login_url="accounts:login")
def registry_list(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    ga_only = request.GET.get("ga") == "1"
    unlinked_only = request.GET.get("unlinked") == "1"

    rows = MemberRegistry.objects.select_related("linked_profile__user").all()
    if q:
        rows = rows.filter(
            Q(full_name_ar__icontains=q) | Q(membership_number__icontains=q) |
            Q(national_id__icontains=q) | Q(assembly_position__icontains=q)
        )
    if ga_only:
        rows = rows.filter(is_general_assembly=True)
    if unlinked_only:
        rows = rows.filter(linked_profile__isnull=True)

    if request.GET.get("export") == "csv":
        data = [["membership_number", "name_ar", "national_id", "general_assembly", "position", "paid_until", "linked"]]
        for r in rows:
            data.append([
                r.membership_number, r.full_name_ar, r.national_id,
                "yes" if r.is_general_assembly else "no", r.assembly_position,
                r.paid_until.isoformat() if r.paid_until else "",
                "yes" if r.linked_profile_id else "no",
            ])
        return _csv_response("ledger.csv", data)

    from django.core.paginator import Paginator

    page = Paginator(rows, 30).get_page(request.GET.get("page") or 1)
    counts = {
        "total": MemberRegistry.objects.count(),
        "ga": MemberRegistry.objects.filter(is_general_assembly=True).count(),
        "linked": MemberRegistry.objects.filter(linked_profile__isnull=False).count(),
        "unlinked": MemberRegistry.objects.filter(linked_profile__isnull=True).count(),
    }
    return render(request, "accounts/registry_list.html", {
        "page_obj": page,
        "q": q,
        "ga_only": ga_only,
        "unlinked_only": unlinked_only,
        "counts": counts,
        "breadcrumbs": [_("لوحة التحكم"), _("سجل الأعضاء (الدفتر)")],
    })


@user_passes_test(_staff, login_url="accounts:login")
def registry_link(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(MemberRegistry.objects.select_related("linked_profile__user"), pk=pk)
    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    candidates = []
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "unlink":
            if not entry.linked_profile_id:
                messages.info(request, _("هذا السجل غير مرتبط أصلًا."))
                return redirect("core:registry_list")
            linked = entry.linked_profile
            entry.linked_profile = None
            entry.save(update_fields=["linked_profile", "updated_at"])
            record(request.user, "ledger_unlink", f"{entry.membership_number} — {entry.full_name_ar}", f"فك ربط البروفايل: {linked.full_name_ar}")
            messages.success(request, _("تم فك الربط. العضو يبقى ببياناته، وسجل الدفتر أصبح حرًا للربط."))
            return redirect("core:registry_list")
        if action == "link":
            profile_id = request.POST.get("profile_id")
            profile = get_object_or_404(Profile.objects.select_related("user"), pk=profile_id)
            if entry.linked_profile_id:
                messages.error(request, _("هذا السجل مربوط بالفعل — فك الربط أولًا."))
                return redirect("core:registry_link", pk=entry.pk)
            # لا تربط نفس البروفايل بأكثر من سطر في الدفتر
            other = MemberRegistry.objects.filter(linked_profile=profile).exclude(pk=entry.pk).first()
            if other:
                messages.error(request, _("هذا البروفايل مربوط بآخر سجل في الدفتر (%(n)s) — فك ربطه أولًا.") % {"n": other.membership_number})
                return redirect("core:registry_link", pk=entry.pk)
            with transaction.atomic():
                if Profile.objects.filter(membership_number=entry.membership_number).exclude(pk=profile.pk).exists():
                    messages.error(request, _("رقم العضوية %(n)s مستخدم في بروفايل تاني — لن يتم الربط.") % {"n": entry.membership_number})
                    return redirect("core:registry_link", pk=entry.pk)
                old_number = profile.membership_number
                profile.membership_number = entry.membership_number
                if entry.national_id and not profile.national_id:
                    profile.national_id = entry.national_id[:14]
                profile.is_general_assembly = entry.is_general_assembly
                profile.assembly_position = entry.assembly_position
                profile.save(update_fields=["membership_number", "national_id", "is_general_assembly", "assembly_position"])
                entry.linked_profile = profile
                entry.save(update_fields=["linked_profile", "updated_at"])
                _create_paid_membership(entry, profile)
            record(
                request.user, "ledger_link", f"{entry.membership_number} — {entry.full_name_ar}",
                f"ربط البروفايل: {profile.full_name_ar} (كان {old_number})",
            )
            messages.success(request, _("تم الربط: العضو بقى رقم عضويته %(n)s") % {"n": entry.membership_number})
            return redirect("core:registry_list")
        messages.error(request, _("إجراء غير معروف."))
        return redirect("core:registry_link", pk=entry.pk)

    if q:
        pool = Profile.objects.select_related("user").exclude(user__isnull=True)
        candidates = list(
            pool.filter(
                Q(user__phone__icontains=q) | Q(full_name_ar__icontains=q) |
                Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) |
                Q(national_id__icontains=q)
            ).order_by("-joined_at")[:20]
        )
    return render(request, "accounts/registry_link.html", {
        "entry": entry,
        "q": q,
        "candidates": candidates,
        "breadcrumbs": [_("لوحة التحكم"), _("سجل الأعضاء (الدفتر)"), _("ربط")],
    })


def _create_paid_membership(entry: MemberRegistry, profile: Profile):
    """Create the paid subscription period recorded in the ledger (if any)."""
    if not entry.paid_until:
        return
    import calendar
    from datetime import date, timedelta

    user = profile.user
    mtype = MembershipType.objects.filter(is_active=True).order_by("order", "price").first()
    if mtype is None:
        return
    end = entry.paid_until
    previous = date(end.year - 1, end.month, min(end.day, calendar.monthrange(end.year - 1, end.month)[1]))
    start = previous + timedelta(days=1)
    base = entry.last_payment_amount or mtype.price
    Membership.objects.create(
        member=user,
        for_user=user,
        membership_type=mtype,
        start_date=start,
        end_date=end,
        status=Membership.Status.ACTIVE,
        base_amount=base,
        discount_amount=Decimal("0"),
        total_amount=base,
        fine_amount=Decimal("0"),
    )
