from django.contrib import admin

from .models import Attendance, Certificate, Course, CourseEnrollment, CourseEvaluation, CourseGroup


class GroupInline(admin.TabularInline):
    model = CourseGroup
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "sport", "level", "status", "price", "price_type", "capacity", "coach")
    list_filter = ("status", "level", "sport", "gender")
    search_fields = ("name", "name_en", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [GroupInline]


@admin.register(CourseGroup)
class CourseGroupAdmin(admin.ModelAdmin):
    list_display = ("course", "name", "schedule", "capacity", "coach")
    list_filter = ("course",)


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("reference", "beneficiary_name", "course", "status", "fee_amount", "created_at")
    list_filter = ("status", "course")
    search_fields = ("reference", "for_user__phone", "for_dependent__full_name_ar", "for_dependent__membership_number")
    readonly_fields = ("reference", "created_at", "updated_at")
    actions = ["confirm", "complete"]

    @admin.action(description="تأكيد المحدد")
    def confirm(self, request, queryset):
        queryset.update(status=CourseEnrollment.Status.CONFIRMED)

    @admin.action(description="إنهاء المحدد (يصدر شهادات)")
    def complete(self, request, queryset):
        from .services import complete_enrollment

        for enrollment in queryset:
            complete_enrollment(enrollment, coach=request.user)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "session_date", "present", "marked_by")
    list_filter = ("session_date", "present")
    search_fields = ("enrollment__reference", "enrollment__for_user__phone", "enrollment__for_dependent__full_name_ar")


@admin.register(CourseEvaluation)
class CourseEvaluationAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "coach", "rating", "created_at")
    list_filter = ("rating",)


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("number", "enrollment", "recipient_name", "issued_at")
    search_fields = ("number", "enrollment__for_user__phone", "enrollment__for_dependent__full_name_ar")
    readonly_fields = ("number", "issued_at")

    def has_add_permission(self, request):
        return False
