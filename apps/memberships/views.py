"""Memberships views — wizard 3 خطوات + حالة اشتراكي وسجل التواريخ."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.models import Dependent

from .models import Membership, MembershipType
from .services import beneficiary_memberships, current_membership, quote_price, renewal_status_breakdown, request_renewal

SESSION_KEY = "renew_wizard"
STEPS = [(1, "البيانات"), (2, "السعر والكوبون"), (3, "التأكيد")]


def _wizard(request):
    return request.session.get(SESSION_KEY) or {}


def _save_wizard(request, data):
    request.session[SESSION_KEY] = data
    request.session.modified = True


def _clear_wizard(request):
    request.session.pop(SESSION_KEY, None)


@login_required
def renew_step1(request):
    """الخطوة 1: اختار المستفيد + نوع الاشتراك."""
    if request.method == "POST":
        beneficiary = request.POST.get("beneficiary", "self")
        type_id = request.POST.get("membership_type")
        mtype = get_object_or_404(MembershipType, pk=type_id, is_active=True)

        data = _wizard(request)
        data["beneficiary"] = beneficiary if beneficiary == "self" else f"dep:{beneficiary}"
        data["type_id"] = mtype.pk
        data.pop("coupon_code", None)  # تغيير أي شيء يلغي الكوبون
        _save_wizard(request, data)
        return redirect("memberships:renew_step2")

    dependents = request.user.dependents.all()
    types = MembershipType.objects.filter(is_active=True)
    return render(request, "memberships/renew_step1.html", {
        "types": types,
        "dependents": dependents,
        "step": 1,
        "steps": STEPS,
    })


@login_required
def renew_step2(request):
    """الخطوة 2: كوبون + ملخص السعر."""
    data = _wizard(request)
    if not data.get("type_id"):
        return redirect("memberships:renew")

    mtype = get_object_or_404(MembershipType, pk=data["type_id"], is_active=True)
    for_dependent = _resolve_target(request, data)
    fine_kwargs = {"for_dependent": for_dependent} if for_dependent is not None else {"for_user": request.user}

    coupon_message = None
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "apply_coupon":
            code = (request.POST.get("coupon_code") or "").strip()
            data["coupon_code"] = code
            quote, error = quote_price(mtype, code, user=request.user, **fine_kwargs)
            if error:
                data.pop("coupon_code", None)
                coupon_message = ("error", error)
                _save_wizard(request, data)
            else:
                coupon_message = ("success", _("تم تطبيق الكوبون! خصم %(d)s ج.") % {"d": quote.discount} if code else None)
                _save_wizard(request, data)
        elif action == "remove_coupon":
            data.pop("coupon_code", None)
            _save_wizard(request, data)
            coupon_message = ("info", _("تم إزالة الكوبون."))
        elif action == "continue":
            return redirect("memberships:renew_step3")

    quote, error = quote_price(mtype, data.get("coupon_code", ""), user=request.user, **fine_kwargs)
    if error:  # الكوبون لم يعد صالحًا
        quote, _err = quote_price(mtype, "", user=request.user, **fine_kwargs)
        data.pop("coupon_code", None)
        _save_wizard(request, data)

    return render(request, "memberships/renew_step2.html", {
        "mtype": mtype,
        "quote": quote,
        "for_dependent": for_dependent,
        "coupon_message": coupon_message,
        "coupon_code": data.get("coupon_code", ""),
        "step": 2,
        "steps": STEPS,
    })


@login_required
def renew_step3(request):
    """الخطوة 3: مراجعة نهائية وتأكيد الطلب."""
    data = _wizard(request)
    if not data.get("type_id"):
        return redirect("memberships:renew")

    mtype = get_object_or_404(MembershipType, pk=data["type_id"], is_active=True)
    for_dependent = _resolve_target(request, data)
    fine_kwargs = {"for_dependent": for_dependent} if for_dependent is not None else {"for_user": request.user}
    quote, error = quote_price(mtype, data.get("coupon_code", ""), user=request.user, **fine_kwargs)
    quote, error = quote_price(mtype, data.get("coupon_code", ""), user=request.user)
    if error:
        fine_kwargs = {"for_dependent": for_dependent} if for_dependent is not None else {"for_user": request.user}
        quote, _err = quote_price(mtype, "", user=request.user, **fine_kwargs)

    if request.method == "POST":
        if for_dependent is not None:
            membership, err = request_renewal(user=request.user, membership_type=mtype, for_dependent=for_dependent, coupon_code=data.get("coupon_code", ""))
        else:
            membership, err = request_renewal(user=request.user, membership_type=mtype, for_user=request.user, coupon_code=data.get("coupon_code", ""))
        if err:
            messages.error(request, err)
            return redirect("memberships:renew_step2")
        _clear_wizard(request)
        return redirect("payments:checkout", reference=membership.reference)

    return render(request, "memberships/renew_step3.html", {
        "mtype": mtype,
        "quote": quote,
        "for_dependent": for_dependent,
        "step": 3,
        "steps": STEPS,
    })


def _resolve_target(request, data):
    target = (data or {}).get("beneficiary", "self")
    if target.startswith("dep:"):
        return get_object_or_404(Dependent, pk=target.split(":", 1)[1], guardian=request.user)
    return None


@login_required
def renew_done(request, reference: str):
    membership = get_object_or_404(Membership, reference=reference, member=request.user)
    return render(request, "memberships/renew_done.html", {"membership": membership})


@login_required
def my_memberships(request):
    """حالة اشتراكي — أنا + تابعي — والسجل الكامل."""
    targets = renewal_status_breakdown(request.user)
    history = beneficiary_memberships(request.user)
    return render(request, "memberships/my.html", {"targets": targets, "history": history})
