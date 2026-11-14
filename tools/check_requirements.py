# -*- coding: utf-8 -*-
"""فحص: كل مكتبة خارجية مستعملة في المشروع لازم تكون في requirements."""
import ast
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"C:\Users\Administrator\Desktop\Club")
STDLIB = set(sys.stdlib_module_names)
LOCAL = {"apps", "config", "templates", "tools"}
DJANGO = {
    "django", "rest_framework", "django_htmx", "environ", "qrcode", "reportlab",
    "whitenoise", "cloudinary", "storages", "anymail",
}

external = {}
for path in list(ROOT.glob("apps/**/*.py")) + list(ROOT.glob("config/**/*.py")):
    if "migrations" in str(path):
        continue
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        continue
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods = [node.module.split(".")[0]]
        for m in mods:
            if m in STDLIB or m in LOCAL or m in DJANGO:
                continue
            external.setdefault(m, set()).add(path.relative_to(ROOT).as_posix())

reqs = ""
for f in ("base.txt", "prod.txt", "dev.txt"):
    p = ROOT / "requirements" / f
    if p.exists():
        reqs += p.read_text(encoding="utf-8").lower().replace("-", "_")

print("=== مكتبات خارجية مستعملة ===")
missing = []
DEV_ONLY = {"pytest", "black", "ruff", "ipython"}
for mod, files in sorted(external.items()):
    key = mod.lower().replace("-", "_")
    in_req = key in reqs
    if not in_req and key in DEV_ONLY:
        status = "OK (dev only)"
    elif in_req:
        status = "OK "
    else:
        status = "!! ناقصة"
        missing.append(mod)
    print(f"  {status:12s} {mod:20s} ({len(files)} ملف)  e.g. {sorted(files)[0]}")

print()
if missing:
    print("MISSING:", ", ".join(sorted(missing)))
else:
    print("OK: كل المكتبات الخارجية موجودة في requirements")
