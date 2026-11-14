"""Courses views — القائمة، التسجيل، الحصص، الحضور، التقييم، الشهادات."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.seo import course_schema
from apps.tournaments.models import Sport

from .models import Attendance, Certificate, Course, CourseEnrollment, CourseEvaluation, CourseGroup
from .services import attendance_stats, complete_enrollment, enroll


def _can_manage_course(user, course) -> bool:
    return user.is_staff or (course.coach_id and course.coach_id == user.id)


def course_list(request: HttpRequest) -> HttpResponse:
    qs = Course.objects.select_related("sport", "coach").exclude(status=Course.Status.DRAFT)
    sport = request.GET.get("sport", "")
    level = request.GET.get("level", "")
    gender = request.GET.get("gender", "")
    if sport:
        qs = qs.filter(sport__id=sport)
    if level:
        qs = qs.filter(level=level)
    if gender:
        qs = qs.filter(gender=gender)
    return render(request, "courses/list.html", {
        "courses": qs,
        "sports": Sport.objects.all(),
        "current_sport": sport,
        "current_level": level,
        "current_gender": gender,
    })


def course_detail(request: HttpRequest, slug: str) -> HttpResponse:
    course = get_object_or_404(Course.objects.select_related("sport", "coach").prefetch_related("groups"), slug=slug)
    my_enrollment = None
    if request.user.is_authenticated:
        my_enrollment = CourseEnrollment.objects.filter(course=course, member=request.user).exclude(status=CourseEnrollment.Status.CANCELLED).first()
    return render(request, "courses/detail.html", {
        "course": course,
        "my_enrollment": my_enrollment,
        "meta_description": (course.description or course.name)[:160],
        "course_schema": course_schema(course, request),
    })


@login_required
def enroll_view(request: HttpRequest, slug: str) -> HttpResponse:
    course = get_object_or_404(Course, slug=slug)
    if course.status != Course.Status.OPEN:
        messages.error(request, _("باب التسجيل مغلق لهذه الدورة."))
        return redirect(course.get_absolute_url())

    profile = getattr(request.user, "profile", None)
    targets = [("self", (profile.full_name_ar if profile else request.user.get_full_name()), profile.age if profile else None)]
    for dep in request.user.dependents.all():
        targets.append((f"dep:{dep.pk}", dep.full_name_ar, dep.age))

    if request.method == "POST":
        who = request.POST.get("beneficiary", "self")
        group_id = request.POST.get("group") or None
        group = CourseGroup.objects.filter(pk=group_id, course=course).first() if group_id else None
        health = request.POST.get("health_ack") == "on"

        from apps.accounts.models import Dependent

        if who == "self":
            enrollment, err = enroll(user=request.user, course=course, group=group, for_user=True, health_acknowledged=health)
        else:
            dep = get_object_or_404(Dependent, pk=who.split(":", 1)[1], guardian=request.user)
            enrollment, err = enroll(user=request.user, course=course, group=group, for_user=False, dependent=dep, health_acknowledged=health)

        if err:
            messages.error(request, err)
            return redirect("courses:enroll", slug=slug)

        fee = enrollment.fee_amount or 0
        if fee > 0:
            from apps.payments.models import Payment
            from apps.payments.services import create_payment

            payment = create_payment(
                member=request.user,
                amount=fee,
                kind=Payment.Kind.COURSE,
                method=Payment.Method.ONLINE,
                course_enrollment=enrollment,
                note=f"رسوم دورة {course.name}",
            )
            messages.info(request, _("أكمل الدفع خلال 48 ساعة لتأكيد تسجيلك."))
            return redirect("payments:checkout", reference=payment.reference)

        messages.success(request, _("تم تسجيلك في الدورة! نتمنى لك رحلة ممتعة."))
        return redirect("courses:my_courses")

    return render(request, "courses/enroll.html", {"course": course, "targets": targets})


@login_required
def my_courses(request: HttpRequest) -> HttpResponse:
    enrollments = (
        CourseEnrollment.objects.filter(member=request.user)
        .select_related("course", "course__sport", "group")
        .prefetch_related("attendance")
        .order_by("-created_at")
    )
    for e in enrollments:
        e.stats = attendance_stats(e)
    return render(request, "courses/my_courses.html", {"enrollments": enrollments})


@login_required
def manage_courses(request: HttpRequest) -> HttpResponse:
    if request.user.is_staff:
        courses = Course.objects.filter(status__in=[Course.Status.OPEN, Course.Status.ONGOING]).order_by("start_date")
    else:
        courses = Course.objects.filter(coach=request.user).order_by("start_date")
    return render(request, "courses/manage.html", {"courses": courses})


@login_required
def attendance_view(request: HttpRequest, slug: str) -> HttpResponse:
    course = get_object_or_404(Course, slug=slug)
    if not _can_manage_course(request.user, course):
        messages.error(request, _("غير مصرح لك بتسجيل الحضور لهذه الدورة."))
        return redirect(course.get_absolute_url())

    date_str = request.GET.get("date") or timezone.now().date().isoformat()
    try:
        session_date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        session_date = timezone.now().date()

    enrollments = list(
        CourseEnrollment.objects.filter(course=course, status__in=[CourseEnrollment.Status.CONFIRMED, CourseEnrollment.Status.COMPLETED])
        .select_related("for_user", "for_dependent")
        .order_by("for_user__first_name", "for_dependent__full_name_ar")
    )
    existing = {a.enrollment_id: a for a in Attendance.objects.filter(enrollment__course=course, session_date=session_date)}

    if request.method == "POST":
        marked = 0
        for e in enrollments:
            present = request.POST.get(f"present_{e.pk}") == "on"
            Attendance.objects.update_or_create(
                enrollment=e, session_date=session_date,
                defaults={"present": present, "marked_by": request.user},
            )
            marked += 1
        messages.success(request, _("تم حفظ الحضور (%(n)s) جلسة.") % {"n": marked})
        return redirect("courses:attendance", slug=course.slug)

    return render(request, "courses/attendance.html", {
        "course": course,
        "enrollments": enrollments,
        "existing": existing,
        "session_date": session_date,
    })


@login_required
@require_POST
def mark_complete(request: HttpRequest, enrollment_id: int) -> HttpResponse:
    enrollment = get_object_or_404(CourseEnrollment.objects.select_related("course"), pk=enrollment_id)
    if not _can_manage_course(request.user, enrollment.course):
        messages.error(request, _("غير مصرح."))
        return redirect("courses:my_courses")
    certificate = complete_enrollment(enrollment, coach=request.user)
    messages.success(request, _("تم إصدار الشهادة %(n)s.") % {"n": certificate.number})
    return redirect("courses:attendance", slug=enrollment.course.slug)


@login_required
@require_POST
def evaluate(request: HttpRequest, enrollment_id: int) -> HttpResponse:
    enrollment = get_object_or_404(CourseEnrollment, pk=enrollment_id, member=request.user)
    if enrollment.status != CourseEnrollment.Status.COMPLETED:
        messages.error(request, _("التقييم متاح بعد اكتمال الدورة."))
        return redirect("courses:my_courses")
    try:
        rating = int(request.POST.get("rating", "5"))
    except ValueError:
        rating = 5
    rating = max(1, min(5, rating))
    CourseEvaluation.objects.update_or_create(
        enrollment=enrollment,
        defaults={"coach": enrollment.course.coach, "rating": rating, "note": (request.POST.get("note") or "").strip()[:500]},
    )
    messages.success(request, _("شكرًا لتقييمك — رأيك يهمنا!"))
    return redirect("courses:my_courses")


@login_required
def certificate_pdf(request: HttpRequest, certificate_id: int) -> HttpResponse:
    certificate = get_object_or_404(
        Certificate.objects.select_related("enrollment__course", "enrollment__for_user", "enrollment__for_dependent"),
        pk=certificate_id,
    )
    if not (request.user.is_staff or certificate.enrollment.member_id == request.user.id):
        from apps.core.views import forbidden

        return forbidden(request)

    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    from apps.core.models import SiteSettings
    from apps.payments.invoice_pdf import ar, _register_fonts

    _register_fonts()
    site = SiteSettings.load()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # الإطار الزخرفي
    c.setFillColor(colors.HexColor("#081c30"))
    c.rect(0, 0, width, height, fill=1)
    c.setStrokeColor(colors.HexColor("#d4af37"))
    c.setLineWidth(6)
    c.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)
    c.setLineWidth(1.2)
    c.rect(16 * mm, 16 * mm, width - 32 * mm, height - 32 * mm)

    # الشعار + اسم المركز
    c.setFillColor(colors.HexColor("#d4af37"))
    c.setFont("Almarai-Bold", 22)
    c.drawCentredString(width / 2, height - 38 * mm, ar(site.name_ar))
    c.setFillColor(colors.HexColor("#bcd0e0"))
    c.setFont("Almarai", 9)
    c.drawCentredString(width / 2, height - 45 * mm, ar(site.address_ar))

    c.setFillColor(colors.white)
    c.setFont("Almarai-Bold", 30)
    c.drawCentredString(width / 2, height - 70 * mm, ar("شهادة إتمام"))
    c.setFont("Almarai", 12)
    c.setFillColor(colors.HexColor("#9db4c6"))
    c.drawCentredString(width / 2, height - 78 * mm, ar("Certificate of Completion"))

    c.setFillColor(colors.white)
    c.setFont("Almarai", 11)
    c.drawCentredString(width / 2, height - 95 * mm, ar("تُمنح إلى"))
    c.setFillColor(colors.HexColor("#d4af37"))
    c.setFont("Almarai-Bold", 22)
    c.drawCentredString(width / 2, height - 105 * mm, ar(certificate.recipient_name))

    c.setFillColor(colors.white)
    c.setFont("Almarai", 11)
    c.drawCentredString(width / 2, height - 120 * mm, ar("لاجتيازه بنجاح دورة"))
    c.setFont("Almarai-Bold", 15)
    c.drawCentredString(width / 2, height - 130 * mm, ar(certificate.enrollment.course.name))

    c.setFont("Almarai", 10)
    c.setFillColor(colors.HexColor("#9db4c6"))
    c.drawCentredString(width / 2, height - 142 * mm, ar("تحت إشراف مدربي المركز بتاريخ " + timezone.now().date().strftime("%Y/%m/%d")))

    # رقم الشهادة
    c.setFillColor(colors.HexColor("#d4af37"))
    c.setFont("Almarai-Bold", 12)
    c.drawCentredString(width / 2, 32 * mm, ar(f"رقم الشهادة: {certificate.number}"))

    c.showPage()
    c.save()
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{certificate.number}.pdf"'
    return response
