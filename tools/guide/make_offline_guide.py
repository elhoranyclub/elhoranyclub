# -*- coding: utf-8 -*-
"""يبني نسخة أوفلاين من الدليل التفاعلي — ملف HTML واحد لكل دور.

كل ملف فيه أقسام دوره بس + الصور مدمجة base64 (شغّال من غير نت).
الموقع بيOffer الملف اللي يناسب دور المستخدم الحالي.
"""
import base64
import io
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SHOTS = os.path.join(ROOT, "static", "guide", "shots")
OUT = os.path.join(ROOT, "static", "guide")
sys.path.insert(0, os.path.join(ROOT, "apps", "pages"))

from guide_content import ROLE_TITLES, SECTIONS, sections_for  # noqa: E402

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Dubai','Segoe UI',Tahoma,Arial,sans-serif;background:#f4f7fb;color:#152438;direction:rtl;line-height:1.75}
.wrap{max-width:1000px;margin:0 auto;padding:18px 16px 60px}
.head{background:linear-gradient(135deg,#0b1b30,#123055);color:#fff;border-radius:18px;padding:22px 24px;margin-bottom:16px}
.head h1{font-size:26px;font-weight:800;margin-top:4px}
.role{display:inline-block;background:rgba(227,178,60,.16);border:1px solid rgba(227,178,60,.45);color:#f3d78a;
  padding:3px 14px;border-radius:999px;font-size:13px;font-weight:700}
.intro{color:#c3d5ea;font-size:15px;margin-top:10px}
.tabs{display:flex;gap:6px;overflow-x:auto;background:#0e2038;border-radius:14px;padding:5px;margin-bottom:14px}
.tabs button{border:0;background:transparent;color:#c3d5ea;font-family:inherit;font-size:15px;font-weight:700;
  padding:10px 16px;border-radius:10px;cursor:pointer;white-space:nowrap}
.tabs button.active{background:rgba(227,178,60,.16);color:#f3d78a}
.search{margin-bottom:16px}
.search input{width:100%;max-width:460px;padding:11px 16px;border-radius:12px;border:1px solid #cdd9e8;font-family:inherit;font-size:15px}
.sec{display:none}
.sec.active{display:block}
.sec h2{font-size:23px;color:#0e2a47;font-weight:800;margin:22px 0 6px}
.sec .intro{color:#4a5b72;margin-bottom:14px}
.card{background:#fff;border:1px solid #e2e9f3;border-radius:16px;padding:20px 22px;box-shadow:0 2px 10px rgba(15,35,60,.05)}
.subtitle{font-size:18px;color:#0e2a47;font-weight:800;margin:20px 0 10px;padding-bottom:8px;border-bottom:2px solid rgba(227,178,60,.35)}
.bullets{list-style:none}
.bullets li{position:relative;padding-right:24px;margin-bottom:8px;color:#26374d;line-height:1.85;font-size:16px}
.bullets li::before{content:"";position:absolute;right:4px;top:11px;width:9px;height:9px;border-radius:3px;background:#d4af37}
.steps{list-style:none;counter-reset:s}
.steps li{counter-increment:s;position:relative;padding-right:42px;margin-bottom:11px;color:#26374d;line-height:1.85;font-size:16px}
.steps li::before{content:counter(s);position:absolute;right:0;top:2px;width:29px;height:29px;border-radius:50%;
  background:#0e2a47;color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.gcard{background:linear-gradient(160deg,rgba(15,42,71,.04),rgba(15,42,71,.01));border:1px solid #e2e9f3;border-radius:14px;padding:16px 18px}
.gcard h3{font-size:17px;color:#0e2a47;font-weight:800;margin-bottom:6px}
.gcard p{font-size:15px;color:#3c4d63;line-height:1.8}
.tablewrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:460px}
th,td{padding:10px 13px;border-bottom:1px solid #e6ecf5;text-align:right;font-size:15.5px}
th{background:#0e2038;color:#fff;font-weight:700}
tbody tr:nth-child(even){background:#f8fafd}
.shot{margin:14px 0;text-align:center}
.shot img{border-radius:12px;border:1px solid #dbe4f0;box-shadow:0 6px 18px rgba(15,35,60,.12);width:100%;height:auto}
.shot figcaption{font-size:13px;color:#66788f;margin-top:6px}
.note{background:#fff5e6;border:1px solid #f3d9ae;color:#8a5a12;padding:12px 15px;border-radius:12px;margin-top:12px;font-size:15px}
code{background:#eef2f8;border:1px solid #dbe4f0;border-radius:6px;padding:2px 7px;font-family:Consolas,monospace;direction:ltr;display:inline-block;font-size:.92em}
.foot{text-align:center;margin-top:26px;font-size:12px;color:#8b9cb2}
@media (max-width:640px){.head h1{font-size:21px}.card{padding:16px 14px}.bullets li,.steps li{font-size:15px}}
"""

JS = """
const tabs=[].slice.call(document.querySelectorAll('.tabs button'));
const secs=[].slice.call(document.querySelectorAll('.sec'));
const q=document.getElementById('q');
function show(id){tabs.forEach(t=>t.classList.toggle('active',t.dataset.target===id));
  secs.forEach(s=>s.classList.toggle('active',s.id===id));window.scrollTo({top:0,behavior:'instant'});}
tabs.forEach(t=>t.addEventListener('click',()=>show(t.dataset.target)));
q.addEventListener('input',()=>{const v=q.value.trim();
  if(!v){secs.forEach((s,i)=>s.classList.toggle('active',i===0));if(tabs[0])tabs[0].classList.add('active');return;}
  let first=null;secs.forEach(s=>{const hit=s.textContent.indexOf(v)!==-1;s.classList.toggle('active',hit);
    if(hit&&!first)first=s.id;});
  tabs.forEach(t=>t.classList.toggle('active',t.dataset.target===first));
  if(first){const el=document.getElementById(first);
    window.scrollTo({top:el.getBoundingClientRect().top+window.scrollY-70,behavior:'smooth'});}});
"""

_img_cache = {}


def img_tag(block):
    name = block["file"]
    if name not in _img_cache:
        path = os.path.join(SHOTS, name)
        with open(path, "rb") as fh:
            _img_cache[name] = base64.b64encode(fh.read()).decode()
    cap = f'<figcaption>{block["caption"]}</figcaption>' if block.get("caption") else ""
    width = block.get("width", 420)
    return (f'<figure class="shot"><img src="data:image/jpeg;base64,{_img_cache[name]}" '
            f'style="max-width:{width}px">{cap}</figure>')


def render_block(block):
    kind = block.get("type")
    if kind == "bullets":
        return "<ul class='bullets'>" + "".join(f"<li>{i}</li>" for i in block["items"]) + "</ul>"
    if kind == "steps":
        return "<ol class='steps'>" + "".join(f"<li>{i}</li>" for i in block["items"]) + "</ol>"
    if kind == "cards":
        cells = "".join(f"<div class='gcard'><h3>{t}</h3><p>{b}</p></div>" for t, b in block["items"])
        return f"<div class='cards'>{cells}</div>"
    if kind == "table":
        head = "".join(f"<th>{h}</th>" for h in block["headers"])
        rows = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in block["rows"])
        return f"<div class='tablewrap'><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
    if kind == "image":
        return img_tag(block)
    if kind == "note":
        return f"<p class='note'>{block['text']}</p>"
    if kind == "title":
        return f"<h3 class='subtitle'>{block['text']}</h3>"
    return ""


def build_role(role):
    sections = sections_for(role)
    title = ROLE_TITLES.get(role, "الدليل التفاعلي")
    label = {"guest": "زائر", "member": "عضو", "dataentry": "مدخل بيانات", "admin": "الإدارة"}.get(role, role)

    tabs = "".join(
        f'<button data-target="{s["id"]}"{" class=\"active\"" if i == 0 else ""}>{s["icon"]} {s["label"]}</button>'
        for i, s in enumerate(sections)
    )
    body = []
    for i, s in enumerate(sections):
        blocks = "".join(render_block(b) for b in s["blocks"])
        body.append(
            f'<section class="sec{" active" if i == 0 else ""}" id="{s["id"]}">'
            f'<h2>{s["icon"]} {s["title"]}</h2>'
            f'<p class="intro">{s["intro"]}</p>'
            f'<div class="card">{blocks}</div></section>'
        )

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — مركز شباب الحوراني</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="head">
    <span class="role">{label}</span>
    <h1>{title}</h1>
    <p class="intro">دليل مصوّر بالموقع — كل اللي يخصك، خطوة بخطوة. (نسخة أوفلاين — بتشتغل من غير نت)</p>
  </header>
  <nav class="tabs">{tabs}</nav>
  <div class="search"><input id="q" type="search" placeholder="دوّر في الدليل…"></div>
  {''.join(body)}
  <p class="foot">مركز شباب الحوراني — آخر تحديث 2026-11-12</p>
</div>
<script>{JS}</script>
</body>
</html>"""

    out = os.path.join(OUT, f"offline-{role}.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"{role}: {out} ({os.path.getsize(out)/1_048_576:.2f} MB) — {len(sections)} أقسام")


def main():
    os.makedirs(OUT, exist_ok=True)
    for role in ("guest", "member", "dataentry", "admin"):
        build_role(role)
    # شيل النسخة القديمة اللي كانت فيها كل الأدوار
    old = os.path.join(OUT, "site-guide.html")
    if os.path.exists(old):
        os.remove(old)
        print("removed old site-guide.html (كان بيعرض كل الأدوار)")


if __name__ == "__main__":
    main()
