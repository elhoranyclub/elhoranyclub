from django.contrib import admin
from django.utils import timezone

from .models import Coupon, CouponRedemption, Membership, MembershipRenewal, MembershipType


@admin.register(MembershipType)
class MembershipTypeAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "price", "duration_months", "min_age", "max_age", "is_active", "order")
    list_editable = ("price", "is_active", "order")
    search_fields = ("name_ar", "name_en")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "kind", "value", "valid_from", "valid_to", "usage_limit", "used_count", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("code",)
    readonly_fields = ("used_count",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("reference", "beneficiary_name", "membership_type", "status", "start_date", "end_date", "total_amount")
    list_filter = ("status", "membership_type")
    search_fields = ("reference", "member__phone", "for_user__phone", "for_dependent__full_name_ar", "for_dependent__membership_number")
    readonly_fields = ("reference", "created_at", "updated_at")
    date_hierarchy = "end_date"
    actions = ["activate", "suspend"]

    @admin.action(description="تفعيل الاشتراكات المحددة (من اليوم + المدة)")
    def activate(self, request, queryset):
        from apps.memberships.services import activate_membership

        for membership in queryset:
            activate_membership(membership)

    @admin.action(description="إيقاف الاشتراكات المحددة")
    def suspend(self, request, queryset):
        queryset.update(status=Membership.Status.SUSPENDED)


@admin.register(MembershipRenewal)
class MembershipRenewalAdmin(admin.ModelAdmin):
    list_display = ("membership", "initiator", "created_at")
    list_filter = ("initiator",)
    readonly_fields = [f.name for f in MembershipRenewal._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "user", "membership", "discount_amount", "created_at")
    readonly_fields = [f.name for f in CouponRedemption._meta.fields]

    def has_add_permission(self, request):
        return False
