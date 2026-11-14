from django.contrib import admin

from .audit import AuditLog
from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "phone", "working_hours_ar", "is_registration_open", "announcement_enabled")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = [
        ("الهوية", {"fields": ("name_ar", "name_en", "tagline_ar", "tagline_en", "logo")}),
        ("التواصل", {"fields": ("phone", "whatsapp", "email", "address_ar", "address_en", "map_embed_url", "working_hours_ar", "working_hours_en")}),
        ("التواصل الاجتماعي", {"fields": ("facebook_url", "instagram_url", "youtube_url", "tiktok_url")}),
        ("الهوية البصرية (CSS)", {"fields": ("primary_color", "gold_color", "green_color")}),
        ("الإعلان العاجل والتسجيل", {"fields": ("announcement_enabled", "announcement_text_ar", "announcement_text_en", "is_registration_open", "event_cancel_cutoff_hours")}),
        ("الاشتراكات والغرامات", {"fields": ("late_fine_percent",)}),
        ("النظام", {"fields": ("created_at", "updated_at")}),
    ]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "target", "detail", "actor__phone")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
