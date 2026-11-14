"""Payments views — checkout موحّد (REN- للاشتراك / PAY- لأي عملية)، تأكيد، إيصالات."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import signing
from django.core.signing import BadSignature
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.memberships.models import Membership

from .gateways.base import GatewayNotConfigured, get_gateway
from .invoice_pdf import render_invoice_pdf
from .models import Invoice, Payment, PaymentProof
from .services import confirm_payment, create_payment, record_wallet_proof, review_proof

logger = logging.getLogger(__name__)

MOCK_TOKEN_SALT = "pay-mock-token"


def _staff_required(user):
    return user.is_authenticated and user.is_staff


def _validate_image(uploaded_file) -> tuple[bool, str]:
    if uploaded_file.size > 5 * 1024 * 1024:
        return False, _("حجم الصورة أكبر من 5 ميجابايت.")
    try:
        from PIL import Image

        img = Image.open(uploaded_file)
        img.verify()
        uploaded_file.seek(0)
        return True, ""
    except Exception:
        return False, _("الملف ليس صورة صالحة.")


# ---------------------------------------------------- payables resolution

@login_required
def checkout(request: HttpRequest, reference: str) -> HttpResponse:
    membership, payment = _resolve_payable(request, reference)
    if membership is None and payment is None:
        messages.error(request, _("الطلب غير موجود."))
        return redirect("core:home")
    pending = membership.payments.order_by("-created_at").first() if membership else payment
    return render(request, "payments/checkout.html", {
        "reference": reference,
        "membership": membership,
        "payment": pending,
        "payable_label": (membership.membership_type.name_ar if membership else payment.get_kind_display()),
        "total": (membership.total_amount if membership else payment.amount),
    })


def _resolve_payable(request, reference):
    """REN-… → (membership, None) | PAY-… → (None, payment)."""
    if reference.startswith("REN-"):
        try:
            membership = Membership.objects.select_related("membership_type").get(reference=reference, member=request.user)
            return membership, None
        except Membership.DoesNotExist:
            return None, None
    if reference.startswith("PAY-"):
        try:
            payment = Payment.objects.select_related("membership").get(reference=reference, member=request.user)
            return None, payment
        except Payment.DoesNotExist:
            return None, None
    return None, None


def _pending_membership_payment(membership, method: str) -> Payment:
    payment = membership.payments.filter(status=Payment.Status.PENDING, method=method).first()
    if payment is None:
        payment = create_payment(
            member=membership.member,
            amount=membership.total_amount,
            kind=Payment.Kind.MEMBERSHIP,
            method=method,
            membership=membership,
        )
    return payment


def _select_method_for(reference: str, request, method: str) -> Payment:
    if reference.startswith("REN-"):
        membership = get_object_or_404(Membership, reference=reference, member=request.user, status=Membership.Status.PENDING)
        return _pending_membership_payment(membership, method)
    payment = get_object_or_404(Payment, reference=reference, member=request.user, status=Payment.Status.PENDING)
    if payment.method != method:
        payment.method = method
        payment.save(update_fields=["method", "updated_at"])
    return payment


@login_required
@require_POST
def pay_online(request: HttpRequest, reference: str) -> HttpResponse:
    payment = _select_method_for(reference, request, Payment.Method.ONLINE)
    if payment.status != Payment.Status.PENDING:
        messages.error(request, _("لا يمكن الدفع لعملية مكتملة."))
        return redirect("payments:receipt", reference=payment.reference)
    gateway = get_gateway()
    try:
        result = gateway.create_checkout(payment)
    except GatewayNotConfigured as exc:
        # البوابة مش مهيّأة (مفاتيح ناقصة) — مش خطأ في طلب العضو
        logger.warning("payment gateway not configured: %s", exc)
        messages.error(request, _("بوابة الدفع مش مهيّأة لسه — اختر الدفع نقدي في المركز."))
        return redirect("payments:checkout", reference=reference)
    except Exception as exc:
        logger.error("gateway error: %s", exc)
        messages.error(request, _("بوابة الدفع غير متاحة حاليًا — اختر طريقة أخرى."))
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        return redirect("payments:checkout", reference=reference)

    payment.provider = gateway.name
    payment.provider_ref = payment.provider_ref or f"MOCK-{payment.reference}"
    payment.save(update_fields=["provider", "provider_ref", "updated_at"])

    if result.get("kind") == "mock":
        token = signing.dumps({"ref": payment.reference}, salt=MOCK_TOKEN_SALT)
        return redirect("payments:mock_pay", token=token)
    return redirect(result["url"])


@login_required
def mock_pay(request: HttpRequest, token: str) -> HttpResponse:
    try:
        data = signing.loads(token, salt=MOCK_TOKEN_SALT, max_age=30 * 60)
    except BadSignature:
        messages.error(request, _("رابط الدفع منتهي أو غير صالح — ابدأ من جديد."))
        return redirect("memberships:renew")
    payment = get_object_or_404(Payment.objects.select_related("membership", "membership__membership_type"), reference=data["ref"], member=request.user)
    if request.method == "POST":
        result = confirm_payment(payment)
        messages.success(request, result.message)
        return redirect("payments:receipt", reference=payment.reference)
    return render(request, "payments/mock_pay.html", {"payment": payment})


@login_required
@require_POST
def pay_wallet(request: HttpRequest, reference: str) -> HttpResponse:
    image = request.FILES.get("proof_image")
    if not image:
        messages.error(request, _("ارفع صورة الإيصال أولًا."))
        return redirect("payments:checkout", reference=reference)
    ok, err = _validate_image(image)
    if not ok:
        messages.error(request, err)
        return redirect("payments:checkout", reference=reference)
    try:
        amount_claimed = Decimal((request.POST.get("amount_claimed") or "0").strip())
    except InvalidOperation:
        amount_claimed = Decimal("0")

    method = Payment.Method.INSTAPAY if request.POST.get("channel") == "instapay" else Payment.Method.WALLET
    payment = _select_method_for(reference, request, method)
    record_wallet_proof(
        payment=payment,
        image=image,
        amount_claimed=amount_claimed,
        operation_number=request.POST.get("operation_number", ""),
    )
    messages.success(request, _("استلمنا إيصالك — الموظف سيراجعه ويفعّل اشتراكك."))
    return redirect("payments:receipt", reference=payment.reference)


@login_required
@require_POST
def pay_cash(request: HttpRequest, reference: str) -> HttpResponse:
    payment = _select_method_for(reference, request, Payment.Method.CASH)
    return redirect("payments:cash", reference=payment.reference)


@login_required
def cash(request: HttpRequest, reference: str) -> HttpResponse:
    payment = get_object_or_404(Payment.objects.select_related("membership", "membership__membership_type"), reference=reference, member=request.user)
    return render(request, "payments/cash.html", {"payment": payment})


@login_required
def my_payments(request: HttpRequest) -> HttpResponse:
    payments = Payment.objects.filter(member=request.user).select_related("membership").order_by("-created_at")[:50]
    return render(request, "payments/my_payments.html", {"payments": payments})


# ---------------------------------------------------------------- receipt

def _can_view_payment(user, payment) -> bool:
    return user.is_staff or payment.member_id == user.id


@login_required
def receipt(request: HttpRequest, reference: str) -> HttpResponse:
    payment = get_object_or_404(Payment.objects.select_related("membership", "membership__membership_type", "member", "tournament_registration"), reference=reference)
    if not _can_view_payment(request.user, payment):
        messages.error(request, _("غير مصرح لك بمشاهدة هذا الإيصال."))
        return redirect("core:home")
    invoice = getattr(payment, "invoice", None)
    return render(request, "payments/receipt.html", {"payment": payment, "invoice": invoice})


@login_required
def invoice_pdf(request: HttpRequest, reference: str) -> HttpResponse:
    payment = get_object_or_404(Payment.objects.select_related("membership", "member"), reference=reference)
    if not _can_view_payment(request.user, payment):
        from apps.core.views import forbidden

        return forbidden(request)
    invoice = getattr(payment, "invoice", None)
    from apps.core.models import SiteSettings

    site = SiteSettings.load()
    profile = getattr(payment.member, "profile", None)
    pdf_bytes = render_invoice_pdf(
        payment, invoice,
        center_name=site.name_ar,
        address=site.address_ar,
        phone=site.phone,
        member_name=(profile.full_name_ar if profile else payment.member.get_full_name()),
        membership_number=(profile.membership_number if profile else "—"),
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{(invoice.number if invoice else payment.reference)}.pdf"'
    return response


# ------------------------------------------------------------------ staff

@user_passes_test(_staff_required, login_url="accounts:login")
def staff_review(request: HttpRequest) -> HttpResponse:
    proofs = PaymentProof.objects.filter(status=PaymentProof.Status.PENDING).select_related(
        "payment", "payment__member", "payment__membership", "payment__membership__membership_type"
    ).order_by("created_at")
    cash_payments = Payment.objects.filter(status=Payment.Status.PENDING, method=Payment.Method.CASH).select_related(
        "member", "membership", "membership__membership_type"
    ).order_by("created_at")
    return render(request, "payments/review.html", {"proofs": proofs, "cash_payments": cash_payments})


@user_passes_test(_staff_required, login_url="accounts:login")
@require_POST
def staff_confirm_cash(request: HttpRequest, reference: str) -> HttpResponse:
    payment = get_object_or_404(Payment, reference=reference, method=Payment.Method.CASH)
    result = confirm_payment(payment, actor=request.user, note=(request.POST.get("note") or "").strip())
    getattr(messages, "success" if result.ok else "error")(request, result.message)
    return redirect("payments:staff_review")


@user_passes_test(_staff_required, login_url="accounts:login")
@require_POST
def staff_review_proof(request: HttpRequest, proof_id: int, action: str) -> HttpResponse:
    proof = get_object_or_404(PaymentProof, pk=proof_id)
    note = (request.POST.get("note") or "").strip()
    if action == "confirm":
        ok, msg = review_proof(proof, confirmed=True, reviewer=request.user, note=note)
    elif action == "reject":
        ok, msg = review_proof(proof, confirmed=False, reviewer=request.user, note=note or _("إيصال غير مطابق"))
    else:
        ok, msg = False, _("إجراء غير معروف.")
    getattr(messages, "success" if ok else "error")(request, msg)
    return redirect("payments:staff_review")


@login_required
def proof_file(request: HttpRequest, proof_id: int) -> HttpResponse:
    proof = get_object_or_404(PaymentProof.objects.select_related("payment"), pk=proof_id)
    if not (request.user.is_staff or proof.payment.member_id == request.user.id):
        from apps.core.views import forbidden

        return forbidden(request)
    from django.core.files.storage import default_storage

    file_handle = default_storage.open(proof.image.name, "rb")
    response = HttpResponse(file_handle.read(), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response


# ---------------------------------------------------------------- webhook

@csrf_exempt
@require_POST
def webhook(request: HttpRequest) -> HttpResponse:
    try:
        gateway = get_gateway()
    except GatewayNotConfigured as exc:
        logger.warning("webhook rejected (gateway not configured): %s", exc)
        return HttpResponse("gateway not configured", status=400)
    ok, data = gateway.verify_webhook(request.headers, request.body)
    if not ok:
        logger.warning("webhook rejected: %s", data)
        return HttpResponse("invalid signature", status=400)

    provider_ref = data.get("provider_ref") or data.get("id")
    reference = data.get("reference") or data.get("order_reference")
    payment = Payment.objects.filter(provider_ref=provider_ref).first() if provider_ref else None
    if payment is None and reference:
        payment = Payment.objects.filter(reference=reference).first()
    if payment is None:
        logger.warning("webhook: payment not found (provider_ref=%s reference=%s)", provider_ref, reference)
        return HttpResponse("ok (payment not found)", status=200)

    result = confirm_payment(payment, note="webhook")
    return HttpResponse("ok (duplicate)" if result.already_paid else "ok", status=200)
