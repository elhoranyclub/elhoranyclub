# -*- coding: utf-8 -*-
"""اختبار القبول الشامل — بيشغّل كل الفحوصات ويكتب تقرير نهائي.

    python tools/acceptance/run_acceptance.py [--base http://127.0.0.1:8080]
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

ROOT = r"C:\Users\Administrator\Desktop\Club"
os.chdir(ROOT)
sys.path.insert(0, ROOT)

PY = sys.executable
REPORT = os.path.join(ROOT, "تقرير_الاختبار_النهائي.md")


def run(cmd, env=None, timeout=1800):
    print("\n>>>", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=timeout)
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(out.strip().splitlines()[-6:])
    print(f"    exit={proc.returncode} · {tail}")
    return proc.returncode, out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--skip-e2e", action="store_true")
    args = parser.parse_args()

    sections = []

    # ١) فحوصات Django
    steps = []

    code, out = run([PY, "manage.py", "check"])
    steps.append(("فحص إعدادات Django", code == 0 and "no issues" in out, out.strip().splitlines()[-1] if out.strip() else ""))

    env = dict(os.environ)
    env.update({
        "SECRET_KEY": "deploy-check-only-" + "x" * 60,
        "ALLOWED_HOSTS": "club.example.com",
        "CSRF_TRUSTED_ORIGINS": "https://club.example.com",
        "DEBUG": "False",
    })
    code, out = run([PY, "manage.py", "check", "--deploy", "--settings=config.settings.prod"], env=env)
    warns = [l for l in out.splitlines() if l.startswith("?:")]
    steps.append(("فحص إعدادات الإنتاج (--deploy)", code == 0, f"{len(warns)} تحذير" + (f": {warns[0][:90]}" if warns else "")))

    code, out = run([PY, "manage.py", "makemigrations", "--check", "--dry-run"])
    steps.append(("مفيش موديل ناقص migration", code == 0, "No changes detected" if code == 0 else out.strip()[-120:]))

    code, out = run([PY, "manage.py", "collectstatic", "--noinput", "--dry-run"])
    steps.append(("collectstatic شغال", code == 0, out.strip().splitlines()[-1] if out.strip() else ""))

    code, out = run([PY, "-m", "pytest", "-q"], timeout=2400)
    summary = [l for l in out.splitlines() if "passed" in l or "failed" in l]
    steps.append(("اختبارات pytest", code == 0, summary[-1] if summary else out.strip()[-120:]))

    sections.append(("فحوصات الكود (Django)", steps))

    # ٢) اختبار المتصفح
    e2e = None
    if not args.skip_e2e:
        code, out = run(["node", "tools/acceptance/e2e_check.mjs", args.base,
                         r"C:\Users\Administrator\AppData\Local\Temp\opencode\acceptance"], timeout=1800)
        results_path = r"C:\Users\Administrator\AppData\Local\Temp\opencode\acceptance\acceptance_results.json"
        if os.path.exists(results_path):
            with open(results_path, encoding="utf-8") as fh:
                e2e = json.load(fh)

    # ٣) التقرير
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = ["# تقرير الاختبار النهائي — مركز شباب الحوراني\n"]
    md.append(f"- **التاريخ:** {now}")
    md.append(f"- **النسخة المختبَرة:** localhost/شبكة محلية (SQLite) — الكود نفسه بتاع الإنتاج")
    md.append(f"- **الرابط:** {args.base}\n")

    md.append("## ١) فحوصات الكود\n")
    md.append("| الفحص | النتيجة | ملاحظة |")
    md.append("|---|---|---|")
    for name, ok, note in sections[0][1]:
        md.append(f"| {name} | {'✅' if ok else '❌'} | {note} |")

    if e2e:
        passed = sum(1 for r in e2e if r["ok"])
        groups = {}
        for r in e2e:
            groups.setdefault(r["group"], [0, 0])
            groups[r["group"]][0 if r["ok"] else 1] += 1
        md.append("\n## ٢) اختبار المتصفح (كل الصفحات والتدفّقات)\n")
        md.append(f"**النتيجة: {passed}/{len(e2e)} ناجح**\n")
        md.append("| المجموعة | ناجح | فاشل |")
        md.append("|---|---|---|")
        for g, (p, f) in groups.items():
            md.append(f"| {g} | {p} | {f} |")
        failed = [r for r in e2e if not r["ok"]]
        if failed:
            md.append("\n### ❌ فاشل\n")
            for r in failed:
                md.append(f"- **[{r['group']}]** {r['name']} {('— ' + r['note']) if r['note'] else ''}")
        md.append("\n### التفاصيل\n")
        cur = ""
        for r in e2e:
            if r["group"] != cur:
                cur = r["group"]
                md.append(f"\n**{cur}**\n")
            md.append(f"- {'✅' if r['ok'] else '❌'} {r['name']}" + (f" _({r['note']})_" if r["note"] else ""))

    md.append("""
## ٣) اللي لسه ديمو — لازم يتعمل قبل ما الموقع يطلع للعامة

| # | الحاجة | الحالة | المطلوب |
|---|---|---|---|
| 1 | **الدفع** | وهمي (mock) — أي عملية بتتأكد من غير فلوس | ربط `PAYMENT_PROVIDER=paymob` + المفاتيح في `.env` على السيرفر |
| 2 | **كود التحقق (OTP)** | شغال بالإيميل (Brevo) | التأكد إن `EMAIL_BACKEND=smtp` + بيانات Brevo صح على السيرفر، أو ربط `NOTIFICATIONS_PROVIDER=whatsapp` |
| 3 | **حسابات التجربة** | موجودة (عضو / مدخل بيانات / سوبر أدمن) | تتغيّر أو تتشال قبل النشر |
| 4 | **بيانات الديمو** | مركز + أخبار + بطولات + رحلات وهمية | تراجع/تتشال من الداتابيز |
| 5 | **فيديوهات التدريب** | `static/guide/guide-<role>.mp4` (٤ ملفات · ٢.٦–٣.٢ ميجا) + الدليل التفاعلي | `collectstatic` على السيرفر عشان توصل للمتصفح |
| 6 | **migration جديد** | `accounts.0003_profile_guide_seen` + `accounts.0006_profile_guide_seen_role` | `python manage.py migrate` على قاعدة Neon |
| 7 | **صورة المعرض** | فيديو ديمو (رابط يوتيوب) في `seed_core` | يتشال قبل النشر |

## ٤) أوامر الرفع على النسخة الحقيقية (Neon)

```bash
# 1) المتغيرات (على منصة النشر)
#    DATABASE_URL=postgresql://USER:PASSWORD@HOST-pooler.REGION.aws.neon.tech/DB?sslmode=require
#    SECRET_KEY=<قوي>  DEBUG=False  ALLOWED_HOSTS=<دومينك>
#    CSRF_TRUSTED_ORIGINS=https://<دومينك>
#    USE_CLOUDINARY=True + CLOUDINARY_*   PAYMENT_PROVIDER=paymob + PAYMOB_*
#    EMAIL_BACKEND=smtp + EMAIL_HOST/USER/PASSWORD   (Brevo)

# 2) الترحيل + تجميع الملفات (بإعدادات prod!)
python manage.py migrate --settings=config.settings.prod
python manage.py collectstatic --noinput --settings=config.settings.prod

# 3) فحص أخير
python manage.py check --deploy --settings=config.settings.prod
```

> **مهم:** أوامر `collectstatic`/`migrate` في `README`/`Procfile` بتشتغل بإعدادات **dev** افتراضيًا — لازم `--settings=config.settings.prod` (أو تعديل `Procfile`).

## ٥) اختبار النسخة الحقيقية بعد الرفع

```bash
# من جهازك (بعد ما تعمل collectstatic و migrate)
python tools/acceptance/e2e_check.mjs https://<دومينك>
```

السكريبت بيمشي على كل الصفحات والتدفّقات لكل دور (زائر / عضو / مدخل بيانات / أدمن) ويطبع تقرير بالنتايج.
""")

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))
    print("\n>> التقرير اتكتب:", REPORT)


if __name__ == "__main__":
    main()
