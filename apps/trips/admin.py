from django.contrib import admin

from .models import GuardianConsent, Trip, TripBooking, TripPassenger


class PassengerInline(admin.TabularInline):
    model = TripPassenger
    extra = 0
    readonly_fields = ("relation", "full_name", "age", "medical_notes", "present")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("name", "destination", "trip_date", "status", "capacity", "seats_left", "member_price", "guest_price")
    list_filter = ("status",)
    search_fields = ("name", "destination")
    prepopulated_fields = {"slug": ("name",)}
    date_hierarchy = "trip_date"


@admin.register(TripBooking)
class TripBookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "trip", "booked_by", "passengers_count", "total_amount", "status", "created_at")
    list_filter = ("status", "trip")
    search_fields = ("reference", "booked_by__phone", "passengers__full_name")
    readonly_fields = ("reference", "created_at", "updated_at")
    inlines = [PassengerInline]


@admin.register(TripPassenger)
class TripPassengerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "booking", "relation", "age", "present")
    list_filter = ("relation", "present")
    search_fields = ("full_name",)


@admin.register(GuardianConsent)
class GuardianConsentAdmin(admin.ModelAdmin):
    list_display = ("passenger", "guardian", "signature_name", "agreed_at", "ip_address")
    readonly_fields = [f.name for f in GuardianConsent._meta.fields]

    def has_add_permission(self, request):
        return False
