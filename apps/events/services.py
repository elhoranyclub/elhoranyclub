"""Registration logic — atomic capacity check with a row lock to kill races."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils.translation import gettext as _

from .models import Event, EventRegistration

logger = logging.getLogger(__name__)


def _send_promotion_payment_link(registration) -> None:
    """إشعار شخص اترقّى من قائمة الانتظار بفعالية مدفوعة: حجزه بانتظار الدفع."""
    try:
        from apps.notifications.services import notify_user
        from apps.payments.models import Payment
        from apps.payments.services import create_payment

        payment = create_payment(
            member=registration.user,
            amount=registration.event.price,
            kind=Payment.Kind.EVENT,
            method=Payment.Method.ONLINE,
            event_registration=registration,
            note=f"رسوم {registration.event.title}",
        )
        notify_user(
            user=registration.user,
            type="system",
            code=None,
            subject=_("فضى مكان في الفعالية — أكمل الدفع"),
            body=_("اترقيت من قائمة الانتظار لفعالية «%(name)s» — حجزك مؤكد مؤقتًا. أكمل الدفع خلال 48 ساعة وإلا سيُعاد المكان لغيرك.") % {"name": registration.event.title},
            action_url=f"/payments/checkout/{payment.reference}/",
        )
    except Exception:
        logger.warning("promotion payment link failed for registration %s", registration.pk, exc_info=True)


@dataclass
class RegistrationResult:
    ok: bool
    message: str
    registration: EventRegistration | None = None


def register_for_event(event: Event, user) -> RegistrationResult:
    if event.status != Event.Status.PUBLISHED:
        return RegistrationResult(False, _("هذا النشاط غير متاح للتسجيل."))
    if not event.requires_registration:
        return RegistrationResult(False, _("هذا النشاط لا يتطلب تسجيلًا مسبقًا."))

    with transaction.atomic():
        locked = Event.objects.select_for_update().get(pk=event.pk)
        existing = EventRegistration.objects.filter(event=locked, user=user).first()
        if existing and existing.status != EventRegistration.Status.CANCELLED:
            return RegistrationResult(False, _("أنت مسجل في هذا النشاط بالفعل."), existing)

        # المقاعد تُحجز بالتأكيد + بانتظار الدفع (زي الرحلات)
        taken = locked.registrations.filter(
            status__in=[EventRegistration.Status.CONFIRMED, EventRegistration.Status.PENDING]
        ).count()
        is_full = taken >= locked.capacity
        if locked.price > 0:
            # مدفوعة وسعة متاحة → بانتظار الدفع؛ ممتلئة → قائمة انتظار بدون دفع
            status = EventRegistration.Status.WAITLIST if is_full else EventRegistration.Status.PENDING
        else:
            status = EventRegistration.Status.WAITLIST if is_full else EventRegistration.Status.CONFIRMED

        if existing:  # أُعيد تفعيل تسجيل ملغى سابق
            existing.status = status
            existing.save(update_fields=["status"])
            registration = existing
        else:
            registration = EventRegistration.objects.create(event=locked, user=user, status=status)

    if registration.status == EventRegistration.Status.CONFIRMED:
        return RegistrationResult(True, _("تم تأكيد تسجيلك في النشاط."), registration)
    if registration.status == EventRegistration.Status.PENDING:
        return RegistrationResult(True, _("أكمل الدفع خلال 48 ساعة لتأكيد حجزك."), registration)
    return RegistrationResult(True, _("اكتمل العدد — تم إضافتك إلى قائمة الانتظار، وسنُخطرك عند توفر مكان."), registration)


def cancel_registration(registration: EventRegistration, *, cutoff_hours: int = 24, now=None) -> tuple[bool, str]:
    from django.utils import timezone

    now = now or timezone.now()
    hours_before = (registration.event.start_at - now).total_seconds() / 3600
    if hours_before < cutoff_hours:
        return False, _("فات الأوان للإلغاء — اتصل بالاستقبال مباشرة.")
    if registration.status == EventRegistration.Status.CANCELLED:
        return False, _("التسجيل ملغى بالفعل.")

    with transaction.atomic():
        registration.status = EventRegistration.Status.CANCELLED
        registration.save(update_fields=["status"])
        # أي دفع معلق لهذا التسجيل لم يعد قابلًا للدفع (تأكيد الإلغاء يعطل التفعيل)
        from apps.payments.models import Payment

        Payment.objects.filter(
            event_registration=registration,
            status=Payment.Status.PENDING,
        ).update(status=Payment.Status.FAILED, note=_("أُلغي الحجز — الدفع ملغى تلقائيًا."), updated_at=timezone.now())
        # ترقية أول شخص في قائمة الانتظار إن توفر مكان
        waitlisted = (
            registration.event.registrations.filter(status=EventRegistration.Status.WAITLIST)
            .order_by("created_at")
            .first()
        )
        if waitlisted is not None:
            if registration.event.price > 0:
                # مدفوعة → لا يتأكد حجزه إلا بعد الدفع: يفضل بانتظار الدفع + نبعتله لينك
                waitlisted.status = EventRegistration.Status.PENDING
                waitlisted.save(update_fields=["status", "updated_at"])
                _send_promotion_payment_link(waitlisted)
            else:
                waitlisted.status = EventRegistration.Status.CONFIRMED
                waitlisted.save(update_fields=["status", "updated_at"])
    return True, _("تم إلغاء تسجيلك.")
