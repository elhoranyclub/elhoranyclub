# -*- coding: utf-8 -*-
"""يبني ملفات HTML لكل شريحة (1920×1080) + ملف نص التعليق الصوتي."""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content_roles import ROLES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SLIDES_DIR = os.path.join(HERE, "slides")
ASSETS = "assets"

NAVY = "#0b1b30"
NAVY2 = "#102544"
GOLD = "#e3b23c"
TEAL = "#3fb6a8"
INK = "#0e1b2e"


CSS = """
@font-face{font-family:'Dubai';src:url('assets/DUBAI-REGULAR.TTF') format('truetype');font-weight:400;}
@font-face{font-family:'Dubai';src:url('assets/DUBAI-LIGHT.TTF') format('truetype');font-weight:300;}
@font-face{font-family:'Dubai';src:url('assets/DUBAI-MEDIUM.TTF') format('truetype');font-weight:500;}
@font-face{font-family:'Dubai';src:url('assets/DUBAI-BOLD.TTF') format('truetype');font-weight:700;}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:1920px;height:1080px;overflow:hidden;}
body{
  font-family:'Dubai','Segoe UI',Tahoma,sans-serif;
  direction:rtl; background:
    radial-gradient(1200px 700px at 12% 18%, #17365c 0%, rgba(23,54,92,0) 60%),
    radial-gradient(900px 600px at 88% 85%, #123f52 0%, rgba(18,63,82,0) 62%),
    linear-gradient(135deg,#081527 0%, #0d2038 55%, #0a1729 100%);
  color:#eaf1fb; position:relative;
}
.bg-grid{position:absolute;inset:0;background-image:
   linear-gradient(rgba(255,255,255,.028) 1px,transparent 1px),
   linear-gradient(90deg,rgba(255,255,255,.028) 1px,transparent 1px);
   background-size:64px 64px;}
.glow{position:absolute;width:760px;height:760px;border-radius:50%;
   background:radial-gradient(circle,rgba(227,178,60,.16),rgba(227,178,60,0) 70%);
   top:-260px;right:-220px;}

/* ===== header ===== */
.top{position:absolute;top:0;right:0;left:0;height:118px;display:flex;align-items:center;
   justify-content:space-between;padding:0 72px;border-bottom:1px solid rgba(255,255,255,.08);
   background:linear-gradient(180deg,rgba(8,18,33,.75),rgba(8,18,33,0));}
.brand{display:flex;align-items:center;gap:18px;}
.brand img{height:62px;width:auto;filter:drop-shadow(0 4px 14px rgba(0,0,0,.45));}
.brand .bname{font-size:27px;font-weight:700;letter-spacing:.2px;}
.brand .bsub{font-size:17px;color:#9fb6d2;margin-top:2px;}
.chip{display:inline-flex;align-items:center;gap:10px;background:rgba(227,178,60,.14);
   border:1px solid rgba(227,178,60,.42);color:#f3d78a;padding:9px 22px;border-radius:999px;
   font-size:20px;font-weight:500;}

/* ===== layout ===== */
.stage{position:absolute;top:118px;bottom:96px;right:0;left:0;padding:44px 72px;
   display:flex;gap:56px;align-items:center;}
.text{flex:1 1 46%;min-width:0;}
.visual{flex:1 1 54%;min-width:0;display:flex;justify-content:center;align-items:center;gap:36px;}
h1.title{font-size:58px;line-height:1.25;font-weight:700;color:#fff;margin-bottom:30px;}
h1.title .hl{color:#e3b23c;}
ul.b{list-style:none;}
ul.b li{position:relative;font-size:29px;line-height:1.55;color:#dbe6f5;padding-right:44px;margin-bottom:22px;}
ul.b li::before{content:'';position:absolute;right:6px;top:14px;width:14px;height:14px;border-radius:4px;
   background:#e3b23c;box-shadow:0 0 0 5px rgba(227,178,60,.14);}
ul.b li.warn::before{background:#ef6b6b;box-shadow:0 0 0 5px rgba(239,107,107,.14);}
ul.b li.ok::before{background:#3fb6a8;box-shadow:0 0 0 5px rgba(63,182,168,.14);}
ul.b li b{color:#fff;font-weight:700;}
ul.b li .em{color:#f3d78a;font-weight:700;}
.caption{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);
   font-size:19px;color:#9fb6d2;background:rgba(6,14,26,.72);border:1px solid rgba(255,255,255,.1);
   padding:7px 20px;border-radius:999px;}

/* phone mock */
.phone{width:352px;border-radius:46px;padding:12px;background:linear-gradient(160deg,#2a3d58,#101d2f);
  box-shadow:0 40px 90px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.08);position:relative;}
.phone img{display:block;width:100%;border-radius:36px;background:#fff;}
.phone .notch{display:none;}

/* browser mock */
.browser{width:100%;max-width:860px;border-radius:18px;overflow:hidden;background:#0e1a2c;
  box-shadow:0 40px 90px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.09);}
.browser .bar{display:flex;align-items:center;gap:10px;padding:12px 16px;background:#16263c;direction:ltr;}
.dot{width:12px;height:12px;border-radius:50%;background:#ff5f57;}
.dot.y{background:#febc2e}.dot.g{background:#28c840}
.browser .url{flex:1;background:#0e1a2c;border-radius:8px;padding:6px 14px;font-size:16px;color:#8fa6c4;
   direction:ltr;text-align:left;font-family:'Dubai',sans-serif;}
.browser img{display:block;width:100%;}

/* ===== cards variant ===== */
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;width:100%;}
.card{background:linear-gradient(160deg,rgba(255,255,255,.07),rgba(255,255,255,.02));
   border:1px solid rgba(255,255,255,.11);border-radius:22px;padding:38px 38px 34px;min-height:250px;}
.card.big{min-height:330px;padding:46px 44px 40px;}
.card.big h3{font-size:36px;}
.card.big p{font-size:28px;line-height:1.65;}
.card .num{font-size:22px;color:#0b1b30;background:#e3b23c;width:52px;height:52px;border-radius:14px;
   display:flex;align-items:center;justify-content:center;font-weight:700;margin-bottom:20px;}
.card h3{font-size:31px;font-weight:700;color:#fff;margin-bottom:14px;line-height:1.35;}
.card p{font-size:25px;line-height:1.6;color:#c7d7ea;}

/* ===== title slide ===== */
.title-slide{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
   justify-content:center;text-align:center;padding:0 140px;}
.title-slide .kicker{font-size:26px;color:#e3b23c;letter-spacing:2px;margin-bottom:24px;}
.title-slide h1{font-size:96px;font-weight:700;line-height:1.2;margin-bottom:26px;}
.title-slide h1 .hl{color:#e3b23c;}
.title-slide p{font-size:33px;color:#c7d7ea;max-width:1200px;line-height:1.6;}
.title-slide .logos{display:flex;gap:34px;align-items:center;margin-bottom:36px;}
.title-slide .logos img{height:110px;width:auto;filter:drop-shadow(0 8px 24px rgba(0,0,0,.5));}
.title-slide .phones{display:flex;gap:40px;align-items:flex-end;margin-top:34px;}
.title-slide .phones .phone{width:262px;}
.title-slide .phones .phone:first-child{transform:translateY(26px);}

/* ===== closing ===== */
.closing-wrap{width:100%;display:flex;gap:60px;align-items:flex-start;}
.roles{flex:1.35;}
.role{display:flex;gap:22px;align-items:flex-start;background:rgba(255,255,255,.06);
   border:1px solid rgba(255,255,255,.1);border-radius:18px;padding:20px 24px;margin-bottom:16px;}
.role .tag{flex:0 0 190px;font-size:26px;font-weight:700;color:#e3b23c;}
.role .txt{font-size:24px;color:#cddced;line-height:1.5;}
.accounts{flex:1;}
.accounts h4{font-size:26px;color:#9fb6d2;margin-bottom:14px;font-weight:500;}
.accounts table{width:100%;border-collapse:collapse;font-size:22px;}
.accounts td{padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.09);color:#dbe6f5;}
.accounts td:first-child{color:#f3d78a;font-weight:700;width:42%;}
.accounts code{font-family:Consolas,monospace;direction:ltr;display:inline-block;color:#9fe3d6;font-size:21px;}
.note{font-size:21px;color:#f0b7a0;margin-top:18px;line-height:1.6;}

/* footer */
.footer{position:absolute;bottom:0;right:0;left:0;height:96px;display:flex;align-items:center;
   justify-content:space-between;padding:0 72px;border-top:1px solid rgba(255,255,255,.07);}
.dots{display:flex;gap:9px;align-items:center;}
.dotbar{width:26px;height:5px;border-radius:3px;background:rgba(255,255,255,.18);}
.dotbar.on{background:#e3b23c;}
.dotbar.done{background:rgba(227,178,60,.45);}
.pnum{font-size:19px;color:#8fa6c4;direction:ltr;}
.ftitle{font-size:20px;color:#8fa6c4;}
.dots{direction:ltr;}
"""


def header(chapter, idx):
    return f"""
  <div class="top">
    <div class="brand">
      <img src="assets/logo.svg" alt="logo">
      <div>
        <div class="bname">مركز شباب الحوراني</div>
        <div class="bsub">الموقع الإلكتروني للمركز</div>
      </div>
    </div>
    <div class="chip">{chapter}</div>
  </div>"""


def footer(idx, total, title):
    bars = []
    for i in range(total):
        cls = "on" if i == idx - 1 else ("done" if i < idx - 1 else "")
        bars.append(f'<div class="dotbar {cls}"></div>')
    return f"""
  <div class="footer">
    <div class="dots">{''.join(bars)}</div>
    <div class="ftitle">دليل استخدام الموقع</div>
    <div class="pnum">{idx} / {total}</div>
  </div>"""


def phone(img, caption=None):
    cap = f'<div class="caption">{caption}</div>' if caption else ""
    return f'<div class="phone"><div class="notch"></div><img src="assets/{img}"></div>{cap}'


def browser(img, caption=None):
    cap = f'<div class="caption">{caption}</div>' if caption else ""
    return (
        f'<div class="browser"><div class="bar"><div class="dot"></div><div class="dot y"></div>'
        f'<div class="dot g"></div><div class="url">club-horani.eg</div></div>'
        f'<img src="assets/{img}"></div>{cap}'
    )


def bullets(items):
    out = []
    for it in items:
        cls = ""
        if it.startswith("⚠"):
            cls = "warn"
            it = it[1:].strip()
        elif it.startswith("✅"):
            cls = "ok"
            it = it[1:].strip()
        elif it.startswith("❌"):
            cls = "warn"
            it = it[1:].strip()
        out.append(f'<li class="{cls}">{it}</li>')
    return f'<ul class="b">{"".join(out)}</ul>'


def build_slide(s, total, role_label=""):
    variant = s["variant"]
    if variant == "title":
        imgs = "".join(
            f'<div class="phone"><div class="notch"></div><img src="assets/{i}"></div>' for i in s.get("images", [])
        )
        body = f"""
  <div class="title-slide">
    <div class="logos"><img src="assets/logo.svg"></div>
    <div class="kicker">مركز شباب الحوراني — {role_label}</div>
    <h1><span class="hl">دليل</span> استخدام الموقع</h1>
    <p>{s['subtitle']}</p>
    <div class="phones">{imgs}</div>
  </div>"""
        return (
            f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{s['title']}</title><style>{CSS}</style></head><body>
<div class="bg-grid"></div><div class="glow"></div>{body}</body></html>"""
        )

    if variant == "closing":
        rows = "".join(
            f'<div class="role"><div class="tag">{r}</div><div class="txt">{t}</div></div>' for r, t in s["rows"]
        )
        accounts = s.get("accounts") or []
        if accounts:
            acc = "".join(
                f"<tr><td>{r}</td><td><code>{p}</code></td><td><code>{pw}</code></td></tr>"
                for r, p, pw in accounts
            )
            accounts_html = f"""
       <div class="accounts">
          <h4>حسابات التجربة (لازم تتغير قبل النشر)</h4>
          <table>{acc}</table>
          <div class="note">⚠️ الحسابات دي للتدريب فقط — شيلها أو غيّر كلمات السر قبل الرفع على الاستضافة.</div>
       </div>"""
        else:
            accounts_html = """
       <div class="accounts">
          <h4>محتاج مساعدة؟</h4>
          <p class="text-sm text-slate-600 leading-relaxed">
            ابعتلنا من صفحة «تواصل معنا» وهنرد عليك في أقرب وقت.
            ولو لقيت حاجة مش مظبوطة في الموقع، ابعتلنا كمان عشان نصلّحها.
          </p>
          <div class="note">💡 كل صفحة «اعرف الموقع أكتر» بتتغيّر حسب صلاحيتك: زائر · عضو · مدخل بيانات · إدارة.</div>
       </div>"""
        body = f"""
  {header(s['chapter'], s['id'])}
  <div class="stage" style="flex-direction:column;align-items:stretch;justify-content:center;gap:30px;">
    <h1 class="title" style="margin-bottom:0;">{s['title']}</h1>
    <div class="closing-wrap">
       <div class="roles">{rows}</div>
       {accounts_html}
    </div>
  </div>
  {footer(s['id'], total, s['title'])}"""
    elif variant == "cards":
        items = s.get("cards") or []
        big = "big" if len(items) <= 3 else ""
        cards = "".join(
            f'<div class="card {big}"><div class="num">{i+1}</div><h3>{t}</h3><p>{d}</p></div>'
            for i, (t, d) in enumerate(items)
        )
        body = f"""
  {header(s['chapter'], s['id'])}
  <div class="stage" style="flex-direction:column;align-items:stretch;justify-content:center;gap:38px;">
    <h1 class="title" style="margin-bottom:0;">{s['title']}</h1>
    <div class="cards">{cards}</div>
  </div>
  {footer(s['id'], total, s['title'])}"""
    else:
        variant_name = s["variant"]
        if variant_name == "phone":
            visual = phone(s["image"], s.get("caption"))
        elif variant_name == "phone2":
            visual = phone(s["image"]) + phone(s["image2"])
        elif variant_name == "desktop":
            visual = browser(s["image"], s.get("caption"))
        else:
            visual = ""
        body = f"""
  {header(s['chapter'], s['id'])}
  <div class="stage">
    <div class="text">
      <h1 class="title">{s['title']}</h1>
      {bullets(s['bullets'])}
    </div>
    <div class="visual">{visual}</div>
  </div>
  {footer(s['id'], total, s['title'])}"""

    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{s['title']}</title><style>{CSS}</style></head><body>
<div class="bg-grid"></div><div class="glow"></div>{body}</body></html>"""


def main():
    sys.path.insert(0, HERE)
    from content_roles import ROLES

    assets_src = os.path.join(HERE, "assets")
    total_slides = 0
    narrations = {}

    for role, data in ROLES.items():
        role_dir = os.path.join(SLIDES_DIR, role)
        os.makedirs(role_dir, exist_ok=True)
        assets_dst = os.path.join(role_dir, "assets")
        os.makedirs(assets_dst, exist_ok=True)
        for fname in os.listdir(assets_src):
            shutil.copy2(os.path.join(assets_src, fname), os.path.join(assets_dst, fname))

        slides = data["slides"]
        total = len(slides)
        total_slides += total

        # اللقطات المستعملة في هذا الدور بس (عشان ما ننسخش كل اللقطات لكل دور)
        used = set()
        for s in slides:
            for key in ("image", "image2"):
                if s.get(key):
                    used.add(s[key])
            for img in s.get("images", []) or []:
                used.add(img)
        shots_src = os.path.join(HERE, "shots")
        for img in sorted(used):
            src = os.path.join(shots_src, img)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(assets_dst, img))

        for s in slides:
            html = build_slide(s, total, data["label"])
            path = os.path.join(role_dir, f"slide-{s['id']:02d}.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
        narrations[role] = {
            "label": data["label"],
            "slides": {str(s["id"]): s["narration"] for s in slides},
        }
        print(f"built {total} slides for {role} -> {role_dir}")

    with open(os.path.join(HERE, "narrations.json"), "w", encoding="utf-8") as fh:
        json.dump(narrations, fh, ensure_ascii=False, indent=2)
    print(f"total {total_slides} slides across {len(ROLES)} roles")


if __name__ == "__main__":
    main()
