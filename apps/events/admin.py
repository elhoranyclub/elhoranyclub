from django.contrib import admin

from .models import Event, EventRegistration


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    readonly_fields = ("user", "status", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_at", "status", "capacity", "confirmed_count", "is_free", "price")
    list_filter = ("status", "is_free", "requires_registration")
    search_fields = ("title", "title_en", "location")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at", "confirmed_count")
    date_hierarchy = "start_at"
    inlines = [EventRegistrationInline]


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__phone", "user__first_name", "event__title")
