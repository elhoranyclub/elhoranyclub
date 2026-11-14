# -*- coding: utf-8 -*-
"""يدمج كل فيديو دور على حدة: شرائح + صوت → MP4 + صورة غلاف."""
import json
import os
import shutil
import subprocess
import sys

import imageio_ffmpeg
import mutagen

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
AUDIO = os.path.join(HERE, "audio")
SEG = os.path.join(HERE, "seg")
STATIC = os.path.abspath(os.path.join(HERE, "..", "..", "static", "guide"))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
PAD = 0.7  # سكوت قصير في آخر كل شريحة

ROLE_FILES = {
    "guest": "دليل-الزائر.mp4",
    "member": "دليل-العضو.mp4",
    "dataentry": "دليل-مدخل-البيانات.mp4",
    "admin": "دليل-الإدارة.mp4",
}


def run(args):
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:], file=sys.stderr)
        raise SystemExit(f"ffmpeg failed: {args[:4]}")
    return proc


def build_role(role, slides):
    role_out = os.path.join(OUT, role)
    role_audio = os.path.join(AUDIO, role)
    role_seg = os.path.join(SEG, role)
    os.makedirs(role_seg, exist_ok=True)

    segments = []
    chapters = []
    elapsed = 0.0
    for slide in slides:
        idx = slide["id"]
        img = os.path.join(role_out, f"slide-{idx:02d}.png")
        mp3 = os.path.join(role_audio, f"slide-{idx:02d}.mp3")
        if not os.path.exists(img) or not os.path.exists(mp3):
            print(f"  !! missing {role}/{idx}")
            continue
        dur = mutagen.File(mp3).info.length + PAD
        seg = os.path.join(role_seg, f"seg-{idx:02d}.mp4")
        if not (os.path.exists(seg) and os.path.getsize(seg) > 0):
            run([
                FFMPEG, "-y", "-loop", "1", "-i", img, "-i", mp3,
                "-filter_complex", "[0:v]fps=30,format=yuv420p[v];[1:a]apad=pad_dur=%.2f[a]" % PAD,
                "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}",
                "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-movflags", "+faststart", seg,
            ])
        title = "مقدمة" if idx == 1 else slide.get("title", "")
        chapters.append({
            "seconds": round(elapsed),
            "time": f"{int(elapsed) // 60}:{int(elapsed) % 60:02d}",
            "title": title,
        })
        elapsed += dur
        segments.append(seg)

    listing = os.path.join(role_seg, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for seg in segments:
            fh.write(f"file '{seg.replace(chr(92), '/')}'\n")

    final = os.path.join(HERE, ROLE_FILES[role])
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listing,
         "-c", "copy", "-movflags", "+faststart", final])

    # غلاف (أول فريم) + نسخة ٧٢٠p للموقع
    poster = os.path.join(HERE, f"poster-{role}.jpg")
    run([FFMPEG, "-y", "-ss", "1.5", "-i", final, "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "5", poster])

    web = os.path.join(HERE, f"web-{role}.mp4")
    run([FFMPEG, "-y", "-i", final, "-vf", "scale=-2:720", "-c:v", "libx264", "-crf", "30",
         "-preset", "slow", "-profile:v", "main", "-c:a", "aac", "-b:a", "96k", "-ac", "2",
         "-movflags", "+faststart", web])

    os.makedirs(STATIC, exist_ok=True)
    shutil.copy2(web, os.path.join(STATIC, f"guide-{role}.mp4"))
    shutil.copy2(poster, os.path.join(STATIC, f"guide-{role}-poster.jpg"))

    size = os.path.getsize(final) / 1_048_576
    web_size = os.path.getsize(web) / 1_048_576
    total = sum(mutagen.File(s).info.length for s in segments)
    print(f"  {role}: {ROLE_FILES[role]} — {total:.0f} ثانية · {size:.1f} MB (ويب {web_size:.1f} MB)")
    return {
        "label": LABEL.get(role, role),
        "duration": round(total),
        "chapters": chapters,
        "video": f"guide-{role}.mp4",
        "poster": f"guide-{role}-poster.jpg",
    }


LABEL = {
    "guest": "زائر",
    "member": "عضو",
    "dataentry": "مدخل بيانات",
    "admin": "الإدارة",
}


def main():
    sys.path.insert(0, HERE)
    from content_roles import ROLES

    manifest = {}
    for role, data in ROLES.items():
        print(f"== {role} ({data['label']}) ==")
        manifest[role] = build_role(role, data["slides"])

    # ملف البيانات بتاع الدليل (بتقراه Django لاختيار الفيديو + الفصول)
    data_dir = os.path.abspath(os.path.join(HERE, "..", "..", "apps", "pages", "data"))
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "guide.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("guide.json ->", os.path.join(data_dir, "guide.json"))

    # نسخة ٧٢٠p للفيديوهات في جذر المشروع
    for role, filename in ROLE_FILES.items():
        src = os.path.join(HERE, filename)
        dst = os.path.join(PROJECT, filename.replace("دليل-", "دليل_").replace(".mp4", "_فيديو.mp4"))
        shutil.copy2(src, dst)
        print("copied ->", os.path.basename(dst))


if __name__ == "__main__":
    main()
