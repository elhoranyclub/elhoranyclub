from django.contrib import admin

from .models import Invoice, Payment, PaymentProof, ReferenceCounter, Refund


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "member", "kind", "method", "amount", "status", "created_at")
    list_filter = ("status", "kind", "method")
    search_fields = ("reference", "provider_ref", "member__phone", "member__first_name", "membership__membership_type__name_ar")
    readonly_fields = ("reference", "created_at", "updated_at", "paid_at")
    date_hierarchy = "created_at"
    inlines = [RefundInline]
    actions = ["refund_full"]

    @admin.action(description="تسجيل استرداد كامل للعمليات المحددة")
    def refund_full(self, request, queryset):
        for payment in queryset.filter(status=Payment.Status.PAID):
            Refund.objects.create(payment=payment, amount=payment.amount, reason="استرداد كامل بقرار الإدارة", created_by=request.user)
            payment.status = Payment.Status.REFUNDED
            payment.save(update_fields=["status", "updated_at"])


@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):
    list_display = ("payment", "amount_claimed", "operation_number", "status", "reviewer", "created_at")
    list_filter = ("status",)
    search_fields = ("payment__reference", "payment__member__phone", "operation_number")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "payment", "issued_at")
    search_fields = ("number", "payment__reference", "payment__member__phone")
    readonly_fields = [f.name for f in Invoice._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(ReferenceCounter)
class ReferenceCounterAdmin(admin.ModelAdmin):
    list_display = ("kind", "year", "last_number")
    readonly_fields = [f.name for f in ReferenceCounter._meta.fields]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("payment", "amount", "reason", "created_by", "created_at")
    readonly_fields = [f.name for f in Refund._meta.fields]
