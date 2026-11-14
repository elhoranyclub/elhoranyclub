"""Course services: enrollment with conditions, completion + certificate."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext as _

from .models import Certificate, Course, CourseEnrollment, CourseGroup


def _beneficiary_dates(*, user, for_user: bool, dependent=None):
    if for_user:
        profile = getattr(user, "profile", None)
        return (profile.birth_date if profile else None, profile.gender if profile else "", profile.full_name_ar if profile else (user.get_full_name() or user.phone))
    if dependent is None or dependent.guardian_id != user.id:
        return None, None, None
    return dependent.birth_date, dependent.gender, dependent.full_name_ar


def _age(birth_date):
    if birth_date is None:
        return None
    from django.utils import timezone

    today = timezone.now().date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def enroll(*, user, course: Course, group=None, for_user: bool = True, dependent=None, health_acknowledged: bool = False):
    """تسجيل في دورة — مع السن والجنس والسعة والإقرار الصحي."""
    birth_date, gender, name = _beneficiary_dates(user=user, for_user=for_user, dependent=dependent)
    if name is None:
        return None, _("يمكنك التسجيل لنفسك أو لتابعيك فقط.")

    age = _age(birth_date)
    if age is None and course.age_min > 0:
        return None, _("أضف تاريخ الميلاد في ملفك أولًا.")
    if age is not None and (age < course.age_min or age > course.age_max):
        return None, _("سن اللاعب (%(age)s سنة) غير مناسب لهذه الدورة.") % {"age": age}
    if course.gender != Course.Gender.MIXED and gender and gender != course.gender:
        return None, _("هذه الدورة مخصصة لهذا النوع فقط.")

    if course.requires_medical and not health_acknowledged:
        return None, _("يلزم الإقرار بصحة البيانات الصحية لهذه الدورة.")

    if course.status != Course.Status.OPEN:
        return None, _("باب التسجيل مغلق لهذه الدورة.")

    existing = CourseEnrollment.objects.filter(
        course=course,
        for_user=user if for_user else None,
        for_dependent=None if for_user else dependent,
    ).exclude(status=CourseEnrollment.Status.CANCELLED).first()
    if existing:
        return None, _("أنت مسجل في هذه الدورة بالفعل.")

    with transaction.atomic():
        locked = Course.objects.select_for_update().get(pk=course.pk)
        if group and group.course_id != locked.pk:
            return None, _("المجموعة لا تتبع هذه الدورة.")
        fee = locked.price if locked.price_type != Course.PriceType.FREE else Decimal("0")
        confirmed = locked.enrollments.filter(status=CourseEnrollment.Status.CONFIRMED).count()
        # دورة مدفوعة؟ تبدأ «قيد المراجعة» وبتأكد بعد دفع الرسوم
        if fee > 0:
            status = CourseEnrollment.Status.PENDING
        elif confirmed < locked.capacity:
            status = CourseEnrollment.Status.CONFIRMED
        else:
            status = CourseEnrollment.Status.WAITLIST
        if group is not None:
            group_confirmed = group.enrollments.filter(status=CourseEnrollment.Status.CONFIRMED).count()
            if group_confirmed >= group.capacity and fee == 0:
                status = CourseEnrollment.Status.WAITLIST

        enrollment = CourseEnrollment.objects.create(
            course=locked,
            group=group,
            member=user,
            for_user=user if for_user else None,
            for_dependent=None if for_user else dependent,
            status=status,
            fee_amount=fee,
            health_acknowledged=health_acknowledged,
        )
    return enrollment, None


def complete_enrollment(enrollment: CourseEnrollment, *, coach=None) -> Certificate:
    """إنهاء الدورة + إصدار الشهادة تلقائيًا (إن لم تكن صادرة)."""
    with transaction.atomic():
        enrollment.status = CourseEnrollment.Status.COMPLETED
        enrollment.coach_note = f"أُنهي بواسطة {coach}" if coach else (enrollment.coach_note or "")
        enrollment.save(update_fields=["status", "coach_note", "updated_at"])
        certificate, _created = Certificate.objects.get_or_create(enrollment=enrollment)
    return certificate


def attendance_stats(enrollment: CourseEnrollment):
    total = enrollment.attendance.count()
    present = enrollment.attendance.filter(present=True).count()
    return {"total": total, "present": present, "percent": (round(present * 100 / total) if total else 0)}
