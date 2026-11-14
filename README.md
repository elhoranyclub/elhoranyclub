# مركز شباب الحوراني — Al-Hourani Youth Sports Center
### بوابة رقمية متكاملة لمراكز الشباب الرياضي في مصر / A complete digital portal for Egyptian youth sports centers

[**العربية**](#العربية) · [**English**](#english)

---

## العربية

نظام ويب متكامل لرقمنة كل خدمات المركز الرياضي: اشتراكات وتجديد من الموبايل، بطولات، دورات تدريبية، رحلات، أخبار ومعرض، مع كارت عضوية رقمي وQR، ولوحة تحكم للإدارة — Mobile-First وRTL كامل.

**حالة التنفيذ:** المراحل 0 ← 9 جاهزة (هيكل + حسابات + محتوى + اشتراكات + مدفوعات + بطولات + دورات + رحلات + إشعارات + PWA/API/SEO/أمان). الدليل أدناه للانتقال إلى الإنتاج ونشره — كل خطوة في قسم Neon تم **اختبارها فعليًا على هذا الكود** (dump ← restore على داتابيز جديدة بنجاح، 116 كائن).

### التقنيات
- **Python 3.12+ / Django 5.2 LTS** · Templates + HTMX + Alpine.js + Tailwind CSS
- **django-environ** لقراءة `DATABASE_URL` — التبديل من SQLite إلى PostgreSQL (Neon) **بدون أي تعديل كود**
- **Cloudinary** للوسائط في الإنتاج (`USE_CLOUDINARY=True`)، FileSystemStorage محليًا
- **Django REST Framework** · WhiteNoise للثابت · PWA · Gunicorn · pytest

### التشغيل السريع (Development)
```bash
python -m venv .venv && .venv\Scripts\activate          # Windows
# source .venv/bin/activate                              # Linux/Mac
pip install -r requirements\dev.txt
copy .env.example .env                                   # Windows
# cp .env.example .env                                   # Linux/Mac
python manage.py migrate
python manage.py seed_core --demo                        # نسخة ديمو كاملة للمحتوى
python manage.py createsuperuser
python manage.py runserver                               # 127.0.0.1:8000
python manage.py runserver 0.0.0.0:8000                  # للدخول من التليفون على نفس الشبكة
```
الدخول للتجربة: العربية `/` · الإنجليزية `/en/` · لوحة التحكم `/admin/`
**حسابات الديمو** (بعد `seed_core --demo`): `01000000001 / Demo@12345` (ولي أمر) · `01000000009 / Admin@12345` (سوبر أدمن) · `01000000004 / Demo@12345` (مدرب)

---

## 🚀 النشر على Render (أسرع طريقة للتجربة)

المشروع فيه **كل ملفات Render جاهزة**: `render.yaml` (Blueprint) · `Procfile` · `runtime.txt` · `requirements/prod.txt`.

### ١) جهّز الكود على GitHub
```bash
git init
git add .
git commit -m "مركز شباب الحوراني — النسخة الأولى"
git branch -M main
git remote add origin https://github.com/<اسمك>/<اسم-الريبو>.git
git push -u origin main
```
> `.gitignore` بيستثني `.env` و `db.sqlite3` و `media/` و `staticfiles/` — يعني **البيانات مش هتترفع** (الأمان ✓).
> ملفات `static/guide/` (١٧ ميجا: الفيديوهات + لقطات الدليل) **بتترفع** — دي اللي الموقع محتاجها.

### ٢) قاعدة البيانات على Neon
1. [neon.tech](https://neon.tech) → مشروع جديد → المنطقة الأقرب لك.
2. انسخ **Pooled connection string** (اللي فيه `-pooler`).
3. على Render: **Environment** → ضيف:
   ```
   DATABASE_URL = postgresql://USER:PASSWORD@HOST-pooler.REGION.aws.neon.tech/DBNAME?sslmode=require
   SECRET_KEY  = <مفتاح ٥٠+ حرف — ولّده بـ: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
   ```

### ٣) ارفع على Render
**الطريقة أ (Blueprint):** [dashboard.render.com](https://dashboard.render.com) → **New → Blueprint** → اختر الريبو → Render هيقرأ `render.yaml` ويجهّز كل حاجة (المتغيرات الـ `sync: false` هتطلب منك تعبيها).

**الطريقة ب (يدوي):** **New → Web Service** → اربط الريبو →:
| الحقل | القيمة |
|---|---|
| Runtime | Python |
| Build Command | `pip install -r requirements/prod.txt` |
| Start Command | `gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings.prod --workers 3 --bind 0.0.0.0:$PORT --timeout 60 --access-logfile -` |
| Health Check Path | `/health` |

> الـ `Procfile` فيه نفس الأوامر (و`release` بتعمل `migrate` + `collectstatic` **بإعدادات prod**) — فاتحها في Render بيشتغل لوحده.
> ⚠️ **مهم:** الأوامر لازم تكون بإعدادات **prod** — `manage.py` افتراضيًا بيشتغل بـ `dev`، وده كان بيعمل `migrate` على SQLite بدل Neon. اتصلّح في `Procfile` و `render.yaml`.

### ٤) بعد أول نشر
```
ALLOWED_HOSTS      = <اسم-الخدمة>.onrender.com
CSRF_TRUSTED_ORIGINS = https://<اسم-الخدمة>.onrender.com
```
(اسأل الـ logs أول حاجة — لو الـ URL اتغيّر، حدّثهم.)

### ٥) اختبر النسخة الحقيقية
```bash
python tools/acceptance/e2e_check.mjs https://<اسم-الخدمة>.onrender.com
```
بيطلعلك تقرير بالنتايج (٨٤ فحص: كل الصفحات والتدفّقات لكل دور + الفيديوهات + الفلترة حسب الدور).

### ⚠️ حاجات قبل ما الناس تشوف الموقع
| الحاجة | المطلوب |
|---|---|
| **الدفع** | `PAYMENT_PROVIDER=paymob` + `PAYMOB_API_KEY` + `PAYMOB_INTEGRATION_ID` + `PAYMOB_HMAC_SECRET` (دلوقتي `mock` = وهمي) |
| **كود التحقق** | `EMAIL_BACKEND=smtp` + `EMAIL_HOST/USER/PASSWORD` (Brevo) — أو `NOTIFICATIONS_PROVIDER=whatsapp` |
| **الصور** | `USE_CLOUDINARY=True` + `CLOUDINARY_*` (على Render الـ media مؤقت) |
| **حسابات التجربة** | لازم تتغيّر أو تتشال (`01000000001` · `01099990000` · `01000000009`) |
| **بيانات الديمو** | لازم تراجعها قبل ما الموقع يبقى حي |

---
## النشر على الإنتاج — خطوة بخطوة (تمت تجربته كاملًا على هذا الكود)

### أولاً: نقل SQLite ← PostgreSQL على Neon

1. **صدّر البيانات من SQLite (على ويندوز استخدم PYTHONIOENCODING لتجنب cp1256):**
   ```bash
   set PYTHONIOENCODING=utf-8
   python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission -e sessions -e admin.logentry --indent 2 > backup.json
   ```
   (في لينكس/ماك: `PYTHONIOENCODING=utf-8 python manage.py dumpdata ... > backup.json`)

2. **أنشئ مشروعًا على [neon.tech](https://neon.tech) مع المنطقة الأقرب** (مثلاً `aws-eu-central-1`)، وانسخ **Pooled connection string** (المستضيف فيه `-pooler`) — الـ pooled host + PgBouncer يستوعب cold starts.

3. **حدّث `.env` على السيرفر:**
   ```
   DEBUG=False
   SECRET_KEY=<اكتب 50+ حرف عشوائي — python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
   DATABASE_URL=postgresql://USER:PASSWORD@HOST-pooler.REGION.aws.neon.tech/DBNAME?sslmode=require
   CONN_MAX_AGE=300
   ALLOWED_HOSTS=your-domain.com,your-subdomain.onrender.com,localhost,127.0.0.1
   CSRF_TRUSTED_ORIGINS=https://your-domain.com
   USE_CLOUDINARY=True
   CLOUDINARY_CLOUD_NAME=...
   CLOUDINARY_API_KEY=...
   CLOUDINARY_API_SECRET=...
   ```
   > ملاحظة Neon: بعد الخمول (scale-to-zero) أول اتصال بيتأخر لحظة — اضبط `CONN_MAX_AGE=300` و`connect_timeout=10` (مضبوط تلقائيًا) واستخدم الـ `-pooler` host. `check --deploy` نظيف بعدها.

4. **ثبّت `prod.txt` وحمّل البيانات:**
   ```bash
   pip install -r requirements/prod.txt          # يشمل psycopg[binary] + gunicorn
   python manage.py migrate
   python manage.py loaddata backup.json         # اختبرناها: 116 كائن من SQLite تحملت بلا أخطاء
   ```

5. **صحّح الـ sequences في Postgres** (Django لا يحدّثها من loaddata):
   ```bash
   python manage.py sqlsequencereset core accounts memberships news events tournaments courses trips payments notifications gallery pages api dashboard | python manage.py dbshell
   ```

6. **تحقق:**
   ```bash
   python manage.py check --deploy               # يجب: no issues
   python -m pytest                               # ⚠️ بـ Neon للـ .env شغّلها بدلًا من: set DATABASE_URL=sqlite:///db.sqlite3 && python -m pytest
   ```

### ثانيًا: تشغيل الإنتاج (Gunicorn + WhiteNoise — على أي Ubuntu VPS)
```bash
pip install -r requirements/prod.txt
python manage.py collectstatic --noinput         # جاهز ومُختبر (218 ملف)
python manage.py migrate && python manage.py seed_core
gunicorn config.wsgi:application --workers 3 --bind 0.0.0.0:8000 --timeout 60 --access-logfile - &
```
ثم Nginx كـ reverse proxy + certbot للـ HTTPS:
```nginx
server {
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location /static/ { alias /path/to/project/staticfiles/; expires 30d; }
}
```
اختياريًا عبر systemd:
```ini
[Unit]
Description=Hourani Youth Center
After=network.target
[Service]
WorkingDirectory=/opt/hourani
ExecStart=/opt/hourani/.venv/bin/gunicorn config.wsgi:application --workers 3 --bind 127.0.0.1:8000 --timeout 60
Restart=always
User=hourani
[Install]
WantedBy=multi-user.target
```
أو منصة PaaS (Render/Railway/Heroku-compatible) — يوجد `Procfile` جاهز (`web: gunicorn config.wsgi:application`).

### ثالثًا: النسخ الاحتياطي
- **Neon:** أنشئ branch قبل أي ترقية، و`pg_dump` مجدول يوميًا: `pg_dump "$DATABASE_URL" > backup-$(date +%F).sql`
- **Cloudinary:** صدّر الوسائط عبر `cloudinary-cli` أو من لوحة التحكم (Settings → Media Library)
- **منطقي:** `dumpdata` مجدول + رفعه لمكان آمن

### متغيرات الإنتاج الأساسية (`.env.example` فيه القائمة الكاملة)
`SECRET_KEY` (قوي) · `DEBUG=False` · `ALLOWED_HOSTS` · `DATABASE_URL` · `CONN_MAX_AGE=300` · `USE_CLOUDINARY=True` + `CLOUDINARY_*` · `CSRF_TRUSTED_ORIGINS=https://...` · `PAYMENT_PROVIDER=paymob` + `PAYMOB_*` · `SENTRY_DSN` (اختياري)

---

## هيكل المشروع
```
config/            إعدادات: settings/{base,dev,prod}.py + urls.py (sitemap/robots/health)
apps/              core accounts memberships news events tournaments courses trips
                   payments notifications gallery pages api dashboard
templates/         base.html + components/ + pages/ + accounts/ + payments/ ...
static/            css (tokens/app/forms/components/overrides/print) · js · img · icons · sw.js · manifest
requirements/      base.txt · dev.txt · prod.txt
```

## الأمان والخصوصية
- الأسرار في `.env` فقط (مستبعد من git) · HTTPS+HSTS+secure cookies في `prod.py`
- OTP بمحاولات محدودة + rate limit لتسجيل الدخول · توقيع HMAC على Webhooks + idempotency
- nh3/bleach لتنظيف أي HTML مدخل · لا تُعرض إيصالات إلا لصاحبها أو staff · التحقق من ownership على كل الكائنات
- مبالغ مالية DecimalField · race-safe للسعة (select_for_update) · AuditLog للعمليات المالية

---

## English

Mobile-first, RTL-first web platform digitizing a youth sports center: memberships with one-thumb renewal, tournaments, training courses, trips, news & gallery, QR membership cards, payments (mock now, Paymob-ready), and an admin back-office.

**Status:** Phases 0–9 complete and tested. Deploy guide below — every step was rehearsed on this exact codebase (SQLite dump → fresh restore loaded 116 fixtures with zero errors).

### Quick start (dev)
```bash
pip install -r requirements/dev.txt
cp .env.example .env
python manage.py migrate && python manage.py seed_core --demo
python manage.py runserver
```
Demo accounts: `01000000001 / Demo@12345` (guardian) · `01000000009 / Admin@12345` (superuser) · `01000000004 / Demo@12345` (coach)

### Production rollout (verified)
1. **Dump:** `PYTHONIOENCODING=utf-8 python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission -e sessions -e admin.logentry --indent 2 > backup.json`
2. Create a **Neon** project (EU region), copy the **pooled** connection string with `sslmode=require`
3. `.env`: `DEBUG=False`, strong `SECRET_KEY`, `DATABASE_URL=postgresql://...pooler...?sslmode=require`, `CONN_MAX_AGE=300`, tight `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`, `USE_CLOUDINARY=True`, Cloudinary keys
4. `pip install -r requirements/prod.txt && python manage.py migrate && python manage.py loaddata backup.json`
5. Reset sequences: `python manage.py sqlsequencereset <apps...> | python manage.py dbshell`
6. `python manage.py check --deploy` — clean
7. `collectstatic` (218 files) then `gunicorn config.wsgi:application` behind Nginx + Let's Encrypt, or the included `Procfile` for PaaS platforms
8. Backups: Neon branches/PITR + `pg_dump` + Cloudinary export

### Security & ops
Secrets only via env · HSTS/secure cookies/CSP in `prod.py` · HMAC webhooks + idempotency · nh3 sanitization · owner/staff authorization on every object · `DecimalField` money · `select_for_update` capacity · audit logging on financial actions · `pytest` suite (72 tests).

### Roadmap (done)
Phase 0 skeleton/settings/mobile base → 1 accounts/OTP/QR card → 2 pages/news/events/gallery → 3 memberships → 4 payments → 5 tournaments → 6 courses → 7 trips → 8 notifications/dashboard → 9 PWA/API/SEO/tests → **10 Neon + production (you are here)**.
