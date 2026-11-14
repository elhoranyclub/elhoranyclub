"""Create Django sessions for the three roles so screenshots can be captured without changing passwords."""
import json
import os
import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\Club")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.chdir(r"C:\Users\Administrator\Desktop\Club")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model, login  # noqa: E402
from django.contrib.sessions.backends.db import SessionStore  # noqa: E402
from django.test import RequestFactory  # noqa: E402

ROLES = {
    "member": "01000000001",
    "dataentry": "01099990000",
    "admin": "admin",
}

User = get_user_model()
out = {}
for role, username in ROLES.items():
    user = User.objects.get(username=username)
    request = RequestFactory().get("/")
    request.session = SessionStore()
    login(request, user)
    request.session.save()
    out[role] = {
        "sessionid": request.session.session_key,
        "username": username,
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
    }

path = os.path.join(os.path.dirname(__file__), "sessions.json")
with open(path, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
print("written ->", path)
