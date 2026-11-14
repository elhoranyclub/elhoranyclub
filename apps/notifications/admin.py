from django.contrib import admin

from .models import Notification, NotificationPreference, NotificationTemplate


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "subject_ar", "is_active", "updated_at")
    list_editable = ("is_active",)
    search_fields = ("code", "subject_ar")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "channel", "subject", "read", "sent_at")
    list_filter = ("type", "channel", "read")
    search_fields = ("user__phone", "subject", "body")
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "in_app", "email", "whatsapp", "sms")
    list_editable = ("in_app", "email", "whatsapp", "sms")
    search_fields = ("user__phone",)
