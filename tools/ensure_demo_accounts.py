"""يتأكد إن حسابات التجربة المذكورة في الدليل موجودة وتعمل.

حسابات التدريب (لازم تتغير/تتشال قبل الرفع على الإنتاج):
  - عضو        : 01000000001 / Demo@12345
  - مدخل بيانات : 01099990000 / Demo@12345  (مجموعة «مدخل بيانات»)
  - سوبر أدمن   : 01000000009 / Admin@12345
"""
import os
import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\Club")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.chdir(r"C:\Users\Administrator\Desktop\Club")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402

User = get_user_model()

ACCOUNTS = [
    # phone, password, first, last, staff, superuser, group
    ("01099990000", "Demo@12345", "محمد", "مدخل البيانات", True, False, "مدخل بيانات"),
    ("01000000009", "Admin@12345", "مدير", "المركز", True, True, None),
]

for phone, password, first, last, staff, superuser, group_name in ACCOUNTS:
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
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    print(f"{'created' if created else 'updated'}  {phone}  staff={user.is_staff} "
          f"super={user.is_superuser}  groups={[g.name for g in user.groups.all()]}")

# التحقق من كلمة السر
from django.contrib.auth import authenticate  # noqa: E402

for phone, password, *_ in ACCOUNTS:
    u = authenticate(username=phone, password=password)
    print("login", phone, "->", "OK" if u else "FAIL")

u = User.objects.filter(phone="01000000001").first()
if u:
    u.set_password("Demo@12345")
    u.save()
    print("login 01000000001 ->", "OK" if authenticate(username="01000000001", password="Demo@12345") else "FAIL")
