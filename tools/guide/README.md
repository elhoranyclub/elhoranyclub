# أدوات توليد دليل الموقع (٤ فيديوهات + دليل تفاعلي)

الملفات دي بتولّد **٤ فيديوهات تدريب** (واحد لكل دور) و **دليل تفاعلي** من الدليل المكتوب (`دليل_الموقع.md`):

| الدور | الملف | المدة |
|---|---|---|
| زائر | `دليل_الزائر_فيديو.mp4` | ٢:٥٦ |
| عضو | `دليل_العضو_فيديو.mp4` | ٣:٠٥ |
| مدخل بيانات | `دليل_مدخل_البيانات_فيديو.mp4` | ٢:٣٨ |
| الإدارة | `دليل_الإدارة_فيديو.mp4` | ٣:٠٠ |

الموقع بيختار الفيديو لوحده حسب صلاحية اللي داخل (من `/guide/video/<role>/`).

## الملفات

| الملف | وظيفته |
|---|---|
| `content_roles.py` | **محتوى الشرائح + نص التعليق الصوتي لكل دور** (هنا بتعدّل الكلام) |
| `build_slides.py` | يبني ملفات HTML لكل شريحة (1920×1080) في `slides/<role>/` |
| `render.ps1` | يصوّر كل شريحة PNG عن طريق Chrome headless في `out/<role>/` |
| `tts.py` | يسجّل الصوت **جملة جملة** + سكوتات + معالجة صوت (يساوي الصوت على ١٦ ديسيبل) |
| `assemble.py` | يدمج كل دور في MP4 + أغلفة + يكتب `apps/pages/data/guide.json` + ينسخ لـ `static/guide/` |
| `prepare_guide_images.py` | يضغط لقطات الدليل التفاعلي (`static/guide/shots/*.jpg`) |
| `make_offline_guide.py` | يبني **نسخة أوفلاين لكل دور** (`static/guide/offline-<role>.html`) — أقسام دوره بس + صور مدمجة |
| `capture*.mjs` | تاخد لقطات حقيقية من الموقع بـ Puppeteer |
| `shots/` | اللقطات المستخدمة في الفيديوهات |
| `assets/` | خطوط Dubai + شعار الموقع |

> **مصدر المحتوى واحد:** الدليل التفاعلي (صفحة الموقع) والنسخ الأوفلاين بيتولّدوا من نفس الملف
> `apps/pages/guide_content.py` — فيه أقسام كل دور والفلترة (`ROLE_SECTIONS`).
> أي تعديل في المحتوى بيوصل لكل الأدوات مرة واحدة.


## إعادة التوليد

```powershell
python -m pip install edge-tts imageio-ffmpeg mutagen pillow
cd tools\guide

# ١) شغّل السيرفر الأول على بورت 8123 (من جذر المشروع):
#    python manage.py runserver 127.0.0.1:8123 --noreload
# ٢) لقطات جديدة (اختياري):
python ..\make_sessions.py
node capture.mjs
node capture2.mjs
node capture3.mjs

# ٣) الشرائح والصوت والفيديوهات:
python build_slides.py
powershell -ExecutionPolicy Bypass -File .\render.ps1
python tts.py
python assemble.py

# ٤) الدليل التفاعلي (لقطات مضغوطة + نسخ أوفلاين لكل دور):
python prepare_guide_images.py
python make_offline_guide.py
```

**المخرجات:**
- `static/guide/guide-<role>.mp4` + `guide-<role>-poster.jpg` (للصفحة)
- `apps/pages/data/guide.json` (فصول الفيديو — بتتقرأ من Django)
- `دليل_<الدور>_فيديو.mp4` في جذر المشروع (نسخة ١٠٨٠p)

## ⚠️ قواعد الكتابة في النص (مهمة)

في `narration` **ممنوع أي حرف لاتيني** — عشان النطق ميبقاش غريب:

| بدل | اكتب |
|---|---|
| QR | كيو آر |
| PDF | بي دي إف |
| OTP | كود تحقق |
| CSV | سي إس في |
| STUDENT20 | كود خصم الطلاب |
| YC-2026-000001 | رقم العضوية |
| Django | دجانجو |
| /manage/ | صفحة القوائم الإدارية |
| dashboard | لوحة التحكم |

## ملاحظات

- **الصوت:** `ar-EG-ShakirNeural` (راجل مصري) في `tts.py` (`RATE` / `PITCH` / `PITCH_PATTERN`).
- **جودة الصوت:** جملة جملة + تنويع نبرة + EQ + مضاغط + توحيد على ١٦ ديسيبل.
- `sessions.json` (بيتشال بعد كل استخدام) فيه مفاتيح جلسات دخول مؤقتة — **متشيلوشه في Git**.
- Chrome/Edge مطلوب للتصوير، و`edge-tts` محتاج نت.
