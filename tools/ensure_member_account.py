# -*- coding: utf-8 -*-
"""ينشئ/يعدّل حساب عضو برقم موبايل — مفيد لما حد يقول «مفتحش معايا».

الاستخدام:
    python tools/ensure_member_account.py 01024519625 --name "محمد أحمد" --email a@b.com --password Demo@12345
"""
import argparse
import os
import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\Club")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.chdir(r"C:\Users\Administrator\Desktop\Club")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from apps.accounts.models import Profile  # noqa: E402

User = get_user_model()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phone")
    parser.add_argument("--name", default="")
    parser.add_argument("--email", default="")
    parser.add_argument("--password", default="Demo@12345")
    parser.add_argument("--active", default="1")
    args = parser.parse_args()

    phone = args.phone.strip()
    user, created = User.objects.get_or_create(
        phone=phone,
        defaults={"username": phone},
    )
    user.username = phone
    if args.name:
        parts = args.name.split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
    if args.email:
        user.email = args.email.strip()
    user.is_active = args.active not in ("0", "false", "False")
    user.set_password(args.password)
    user.save()

    profile, _ = Profile.objects.get_or_create(
        user=user,
        defaults={"full_name_ar": args.name or phone},
    )
    if args.name:
        profile.full_name_ar = args.name
        profile.save(update_fields=["full_name_ar"])

    print(f"{'created' if created else 'updated'}  phone={phone}  name={profile.full_name_ar}")
    print(f"  email={user.email or '—'}  active={user.is_active}  password={args.password}")
    print(f"  membership_number={profile.membership_number}")


if __name__ == "__main__":
    main()
