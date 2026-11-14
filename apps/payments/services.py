"""
Payment services: إنشاء عمليات، تأكيد ذري (idempotent)، تفعيل الاشتراك، الفواتير.
كل التعديلات المالية داخل transaction.atomic + select_for_update على صف الـ Payment.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.memberships.services import activate_membership

from .models import Invoice, Payment, PaymentProof

logger = logging.getLogger(__name__)


def create_payment(*, member, amount, kind: str, method: str, membership=None, tournament_registration=None, course_enrollment=None, trip_booking=None, event_registration=None, note: str = "") -> Payment:
    payment = Payment(
        member=member,
        amount=amount,
        kind=kind,
        method=method,
        status=Payment.Status.PENDING,
        membership=membership,
        tournament_registration=tournament_registration,
        course_enrollment=course_enrollment,
        trip_booking=trip_booking,
        event_registration=event_registration,
        note=note,
    )
    payment.save()  # save() يولّد reference
    return payment


@dataclass
class ConfirmResult:
    ok: bool
    message: str
    already_paid: bool = False
    invoice: Invoice | None = None


def confirm_payment(payment: Payment, *, actor=None, note: str = "", mark_method: str | None = None) -> ConfirmResult:
    """يؤكد الدفع — آمن من التكرار ولا ينشئ فواتير مزدوجة ولا يفعّل مرتين."""
    with transaction.atomic():
        locked = Payment.objects.select_for_update().select_related("membership", "membership__membership_type").get(pk=payment.pk)
        if locked.status == Payment.Status.PAID:
            return ConfirmResult(True, _("مؤكد بالفعل."), already_paid=True, invoice=getattr(locked, "invoice", None))
        if locked.status != Payment.Status.PENDING:
            return ConfirmResult(False, _("لا يمكن تأكيد عملية بحالة «%(s)s».") % {"s": locked.get_status_display()})

        locked.status = Payment.Status.PAID
        locked.paid_at = timezone.now()
        if mark_method:
            locked.method = mark_method
        if note and not locked.note:
            locked.note = note
        locked.save(update_fields=["status", "paid_at", "method", "note", "updated_at"])

        invoice, _created = Invoice.objects.get_or_create(payment=locked)
        if locked.membership_id and locked.membership.status != "active":
            activate_membership(locked.membership)
        if locked.tournament_registration_id:
            from apps.tournaments.models import TournamentRegistration

            TournamentRegistration.objects.filter(
                pk=locked.tournament_registration_id,
                status=TournamentRegistration.Status.PENDING,
            ).update(status=TournamentRegistration.Status.ACCEPTED)
        if locked.course_enrollment_id:
            from apps.courses.models import CourseEnrollment

            CourseEnrollment.objects.filter(
                pk=locked.course_enrollment_id,
                status=CourseEnrollment.Status.PENDING,
            ).update(status=CourseEnrollment.Status.CONFIRMED)
        if locked.trip_booking_id:
            from apps.trips.models import TripBooking

            TripBooking.objects.filter(
                pk=locked.trip_booking_id,
                status=TripBooking.Status.PENDING,
            ).update(status=TripBooking.Status.CONFIRMED)
        if locked.event_registration_id:
            from apps.events.models import EventRegistration

            EventRegistration.objects.filter(
                pk=locked.event_registration_id,
                status=EventRegistration.Status.PENDING,
            ).update(status=EventRegistration.Status.CONFIRMED)

        from apps.core.audit import record

        record(actor, "payment.confirmed", target=locked.reference, detail=f"amount={locked.amount} kind={locked.kind}")
        try:
            from apps.notifications.services import notify_user

            notify_user(
                user=locked.member,
                type="payment_confirmed",
                code="payment_confirmed",
                context={"name": locked.member.get_full_name() or locked.member.phone, "ref": locked.reference, "amount": locked.amount},
                action_url=f"/payments/receipt/{locked.reference}/",
            )
        except Exception:
            logger.warning("notify on payment confirm failed", exc_info=True)
    return ConfirmResult(True, _("تم تأكيد الدفع وإصدار الفاتورة."), invoice=invoice)


def record_wallet_proof(*, payment: Payment, image, amount_claimed, operation_number: str = "") -> PaymentProof:
    return PaymentProof.objects.create(
        payment=payment,
        image=image,
        amount_claimed=amount_claimed,
        operation_number=operation_number.strip(),
        status=PaymentProof.Status.PENDING,
    )


def review_proof(proof: PaymentProof, *, confirmed: bool, reviewer, note: str = "") -> tuple[bool, str]:
    """مراجعة إيصال محفظة — التأكيد يفعّل الاشتراك."""
    with transaction.atomic():
        locked = PaymentProof.objects.select_for_update().select_related("payment").get(pk=proof.pk)
        if locked.status != PaymentProof.Status.PENDING:
            return False, _("تمت مراجعة هذا الإيصال بالفعل.")
        locked.status = PaymentProof.Status.CONFIRMED if confirmed else PaymentProof.Status.REJECTED
        locked.reviewer = reviewer
        locked.reviewed_at = timezone.now()
        locked.reviewer_note = note[:255]
        locked.save(update_fields=["status", "reviewer", "reviewed_at", "reviewer_note", "updated_at"])
        if confirmed:
            result = confirm_payment(locked.payment, actor=reviewer, note=f"إيصال {locked.operation_number}".strip())
            return result.ok, result.message
        return True, _("تم رفض الإيصال وإشعار العضو.")
