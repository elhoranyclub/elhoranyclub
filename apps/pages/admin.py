from django.contrib import admin

from .models import BoardMember, ContactMessage, FAQ, Facility


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "icon", "hours", "order")
    list_editable = ("order",)
    search_fields = ("name_ar", "name_en")


@admin.register(BoardMember)
class BoardMemberAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "role_ar", "order")
    list_editable = ("order",)
    search_fields = ("name_ar", "role_ar")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question_ar", "is_active", "order")
    list_filter = ("is_active",)
    list_editable = ("order", "is_active")
    search_fields = ("question_ar", "question_en")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "subject", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("name", "phone", "subject", "message")
    readonly_fields = ("name", "phone", "email", "subject", "message", "created_at", "updated_at")
    actions = ["mark_read"]

    @admin.action(description="تمييز كمقروءة")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)
