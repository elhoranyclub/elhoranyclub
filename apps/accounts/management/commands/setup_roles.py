"""
إعداد صلاحيات الموظفين — أدمن vs مدخل بيانات.
Idempotent: ينشئ/يحدّث المجموعتين في كل تشغيلة.

سوبر أدمن (is_superuser) — خارج النطاق: كل شيء بما فيه حسابات الموظفين والإعدادات.

Usage: python manage.py setup_roles
"""
from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

GROUP_ADMIN = "أدمن"
GROUP_CLERK = "مدخل بيانات"

# صلاحيات أدمن: كل شيء ما عدا الموديلات الحساسة (وإلا DELETE على المالية)
ADMIN_EXCLUDE = {
    # إدارة المستخدمين والموظفين — سوبر أدمن فقط
    ("auth", "user"), ("auth", "group"), ("auth", "permission"),
    ("accounts", "user"), ("accounts", "profile"), ("accounts", "dependent"),
    ("accounts", "otp"), ("accounts", "membershipcounter"),
    # هوية/إعدادات الموقع — سوبر أدمن فقط
    ("core", "sitesettings"), ("core", "auditlog"),
    # مالية: لا حذف سجلات
    ("payments", "invoice"), ("payments", "referencecounter"),
    ("sessions", "session"),
    ("contenttypes", "contenttype"), ("contenttypes", "permission"),
    ("admin", "logentry"),
}
ADMIN_DELETE_BLOCKED_MODELS = {
    ("payments", "payment"),
    ("payments", "refund"),
    ("memberships", "membership"),
    ("memberships", "membershiprenewal"),
}

# مدخل بيانات: قائمة صريحة بالأفعال المسموحة لكل موديل
CLERK_PERMS = {
    # المحتوى — إضافة/تعديل/عرض (بلا حذف)
    ("news", "newsarticle"): ["add", "change", "view"],
    ("news", "newscategory"): ["add", "change", "view"],
    ("news", "tag"): ["add", "change", "view"],
    ("news", "newsimage"): ["add", "change", "view"],
    ("events", "event"): ["add", "change", "view"],
    ("events", "eventregistration"): ["change", "view"],
    ("courses", "course"): ["add", "change", "view"],
    ("courses", "coursegroup"): ["add", "change", "view"],
    ("courses", "courseenrollment"): ["change", "view"],
    ("courses", "attendance"): ["add", "change", "view"],
    ("trips", "trip"): ["add", "change", "view"],
    ("trips", "tripbooking"): ["change", "view"],
    ("gallery", "galleryalbum"): ["add", "change", "delete", "view"],
    ("gallery", "mediaitem"): ["add", "change", "delete", "view"],
    ("tournaments", "tournament"): ["add", "change", "view"],
    ("tournaments", "tournamentcategory"): ["add", "change", "view"],
    ("tournaments", "team"): ["add", "change", "view"],
    ("tournaments", "match"): ["add", "change", "view"],
    ("tournaments", "tournamentregistration"): ["change", "view"],
    # الأعضاء والاشتراكات — تفعيل وتجديد (بلا حذف)
    ("memberships", "membership"): ["add", "change", "view"],
    ("memberships", "membershiprenewal"): ["add", "change", "view"],
    ("memberships", "membershiptype"): ["view"],
    ("memberships", "coupon"): ["view"],
    # مراجعة المدفوعات — بدون حذف
    ("payments", "payment"): ["add", "change", "view"],
    ("payments", "paymentproof"): ["add", "change", "view"],
    # الرسائل الواردة
    ("pages", "contactmessage"): ["change", "view"],
}


def _assign(group: Group, permissions: list[Permission]) -> None:
    group.permissions.set(permissions)


class Command(BaseCommand):
    help = "يجهّز مجموعات الموظفين (أدمن / مدخل بيانات) بالصلاحيات"

    def handle(self, *args, **options):
        admin_perms = self._admin_permissions()
        clerk_perms = self._clerk_permissions()

        admin_group, _ = Group.objects.get_or_create(name=GROUP_ADMIN)
        clerk_group, _ = Group.objects.get_or_create(name=GROUP_CLERK)

        _assign(admin_group, admin_perms)
        _assign(clerk_group, clerk_perms)

        print(f"OK {GROUP_ADMIN}: {len(admin_perms)} permissions")
        print(f"OK {GROUP_CLERK}: {len(clerk_perms)} permissions")

    def _admin_permissions(self) -> list[Permission]:
        perms = []
        for perm in Permission.objects.select_related("content_type"):
            key = (perm.content_type.app_label, perm.content_type.model)
            if key in ADMIN_EXCLUDE:
                continue
            action = perm.codename.split("_", 1)[0]  # add / change / delete / view
            if action == "delete" and key in ADMIN_DELETE_BLOCKED_MODELS:
                continue
            perms.append(perm)
        return perms

    def _clerk_permissions(self) -> list[Permission]:
        perms = []
        for (app, model), actions in CLERK_PERMS.items():
            for action in actions:
                codename = f"{action}_{model}"
                try:
                    perms.append(
                        Permission.objects.get(content_type__app_label=app, content_type__model=model, codename=codename)
                    )
                except Permission.DoesNotExist:
                    self.style.WARNING(f"Missing permission: {app}.{codename}")
        return perms
