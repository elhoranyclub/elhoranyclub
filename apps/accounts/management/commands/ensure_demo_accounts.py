"""
إنشاء/تحديث حسابات التدريب على أي بيئة (محلي أو الإنتاج).

الاستخدام:
    python manage.py ensure_demo_accounts
    python manage.py ensure_demo_accounts --password "كلمة-سر-قوية"

بيعمل:
  - مجموعة «مدخل بيانات» (٧١ صلاحية) + مجموعة «أدمن» (كل الصلاحيات)
  - عضو:        01000000001 / Demo@12345
  - مدخل بيانات: 01099990000 / Demo@12345
  - سوبر أدمن:   01000000009 / Admin@12345

⚠️ الحسابات دي للتدريب فقط — شيلها (أو غيّر كلمات السر) قبل ما الموقع يبقى حي للجمهور.
"""
from __future__ import annotations

import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.core.management import call_command

GROUP_ADMIN = "أدمن"
GROUP_CLERK = "مدخل بيانات"

ACCOUNTS = [
    # phone, password, first, last, staff, superuser, group
    ("01000000001", "Demo@12345", "أحمد", "محمود", False, False, None),
    ("01099990000", "Demo@12345", "محمد", "مدخل البيانات", True, False, GROUP_CLERK),
    ("01000000009", "Admin@12345", "مدير", "المركز", True, True, None),
]


class Command(BaseCommand):
    help = "ينشئ حسابات التدريب ومجموعات الموظفين (عضو / مدخل بيانات / سوبر أدمن)"

    def add_arguments(self, parser):
        parser.add_argument("--password", default="", help="كلمة سر موحّدة لكل الحسابات (مفيدة للإنتاج)")

    def handle(self, *args, **options):
        # الشينل بتاع Render UTF-8، لكن ويندوز ممكن يكون cp1256
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

        User = get_user_model()
        password_override = options.get("password") or ""

        # المجموعات والصلاحيات
        call_command("setup_roles", verbosity=0)
        clerk_group, _ = Group.objects.get_or_create(name=GROUP_CLERK)
        admin_group, _ = Group.objects.get_or_create(name=GROUP_ADMIN)

        for phone, default_password, first, last, staff, superuser, group_name in ACCOUNTS:
            password = password_override or default_password
            user, created = User.objects.get_or_create(
                phone=phone,
                defaults={"username": phone, "first_name": first, "last_name": last},
            )
            user.username = phone
            user.first_name = first
            user.last_name = last
            user.set_password(password)
            user.is_staff = staff
            user.is_superuser = superuser
            user.is_active = True
            user.save()

            if group_name == GROUP_CLERK:
                user.groups.add(clerk_group)
            elif group_name == GROUP_ADMIN:
                user.groups.add(admin_group)
            elif superuser:
                user.groups.add(admin_group)

            profile = getattr(user, "profile", None)
            mnumber = profile.membership_number if profile else "—"

            self.stdout.write(
                f"{'انشئ' if created else 'حدث'}  {phone}  {first} {last}  "
                f"staff={staff} super={superuser} groups={[g.name for g in user.groups.all()]}  "
                f"عضوية={mnumber}"
            )

        self.stdout.write(self.style.SUCCESS("تم - حسابات التدريب جاهزة"))
        self.stdout.write("تحذير: شيلها أو غيّر كلمات السر قبل ما الموقع يبقى حي.")
