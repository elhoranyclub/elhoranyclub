from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Dependent, MemberRegistry, MembershipCounter, MembershipNumberCounter, OTP, Profile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("phone", "first_name", "last_name", "is_active", "is_staff")
    search_fields = ("phone", "first_name", "last_name", "email")
    fieldsets = UserAdmin.fieldsets + (("بيانات إضافية", {"fields": ("phone",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("بيانات إضافية", {"fields": ("phone",)}),)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("membership_number", "full_name_ar", "user", "is_general_assembly", "assembly_position", "joined_at")
    search_fields = ("membership_number", "full_name_ar", "full_name_en", "user__phone", "national_id")
    list_filter = ("is_general_assembly", "gender", "governorate", "shirt_size")
    readonly_fields = ("membership_number", "joined_at", "created_at", "updated_at")
    fieldsets = [
        ("العضوية", {"fields": ("user", "membership_number", "joined_at")}),
        ("البيانات الأساسية", {"fields": ("full_name_ar", "full_name_en", "birth_date", "gender", "photo")}),
        ("اللجنة العمومية", {"fields": ("is_general_assembly", "assembly_position")}),
        ("الرقم القومي والعنوان", {"fields": ("national_id", "governorate", "address")}),
        ("الطوارئ والصحة", {"fields": ("emergency_contact_name", "emergency_contact_phone", "health_notes", "shirt_size")}),
        ("النظام", {"fields": ("created_at", "updated_at")}),
    ]


@admin.register(MemberRegistry)
class MemberRegistryAdmin(admin.ModelAdmin):
    list_display = ("membership_number", "full_name_ar", "national_id", "is_general_assembly", "assembly_position", "paid_until", "linked_profile")
    search_fields = ("full_name_ar", "national_id", "membership_number")
    list_filter = ("is_general_assembly",)
    readonly_fields = ("created_at", "updated_at", "linked_profile")
    ordering = ("membership_number",)


@admin.register(MembershipNumberCounter)
class MembershipNumberCounterAdmin(admin.ModelAdmin):
    list_display = ("id", "last_number")
    readonly_fields = ("last_number",)

    def has_add_permission(self, request):
        return not MembershipNumberCounter.objects.exists()


@admin.register(Dependent)
class DependentAdmin(admin.ModelAdmin):
    list_display = ("membership_number", "full_name_ar", "guardian", "relation", "birth_date")
    search_fields = ("membership_number", "full_name_ar", "guardian__phone", "guardian__first_name")
    readonly_fields = ("membership_number", "created_at", "updated_at")


@admin.register(MembershipCounter)
class MembershipCounterAdmin(admin.ModelAdmin):
    list_display = ("year", "last_number")
    readonly_fields = ("year", "last_number")


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ("phone", "purpose", "created_at", "expires_at", "attempts", "consumed")
    list_filter = ("purpose", "consumed")
    readonly_fields = [f.name for f in OTP._meta.fields]

    def has_add_permission(self, request):
        return False
