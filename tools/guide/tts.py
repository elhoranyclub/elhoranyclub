# -*- coding: utf-8 -*-
"""تسجيل التعليق الصوتي وتحسينه — مقسّم على جمل، مع فواصل طبيعية ومعالجة صوت.

الخطوات لكل شريحة:
  ١) تقسيم النص على جمل.
  ٢) تسجيل كل جملة لوحدها (صوت راجل مصري) مع تنويع بسيط في النبرة.
  ٣) لصق الجمل مع سكوتات قصيرة بين الجمل (أقرب للكلام الطبيعي).
  ٤) معالجة: فلتر للضوضاء المنخفضة + مضاغط + توحيد مستوى الصوت على ١٦ ديسيبل.

المخرجات: audio/<role>/slide-NN.mp3
"""
import asyncio
import json
import os
import re
import subprocess
import sys

import edge_tts
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "ar-EG-ShakirNeural"
RATE = "-4%"
FFMPEG_AUDIO_FILTER = (
    "highpass=f=85,"
    "equalizer=f=250:t=q:w=1:g=-1.5,"
    "equalizer=f=2200:t=q:w=1.4:g=2.2,"
    "equalizer=f=6000:t=q:w=1.5:g=1.5,"
    "acompressor=threshold=-20dB:ratio=2.2:attack=18:release=140:makeup=2,"
    "alimiter=limit=0.95,"
    "loudnorm=I=-16:TP=-1.5:LRA=11"
)

SENT_SPLIT = re.compile(r"(?<=[.!?؟…])\s+")
# تنويع بسيط في النبرة بين الجمل (بيقلل الإحساس المسطّح/الروبوتي)
PITCH_PATTERN = ["-2Hz", "+1Hz", "-1Hz", "+2Hz", "+0Hz"]


def sentences(text):
    parts = [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]
    return parts or [text.strip()]


def make_silence(path, seconds):
    if os.path.exists(path):
        return path
    subprocess.run([
        FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{seconds:.2f}", "-c:a", "libmp3lame", "-b:a", "48k", path,
    ], capture_output=True)
    return path


async def synth_sentence(text, out_path, pitch):
    if os.path.exists(out_path) and os.path.getsize(out_path) > 500:
        return
    comm = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=pitch)
    await comm.save(out_path)


async def synth_role(role, slides, audio_root):
    role_dir = os.path.join(audio_root, role)
    os.makedirs(role_dir, exist_ok=True)
    work = os.path.join(role_dir, "_parts")
    os.makedirs(work, exist_ok=True)

    silence_short = make_silence(os.path.join(work, "sil_030.mp3"), 0.30)
    silence_long = make_silence(os.path.join(work, "sil_055.mp3"), 0.55)

    for slide in slides:
        idx = slide["id"]
        final = os.path.join(role_dir, f"slide-{idx:02d}.mp3")
        if os.path.exists(final) and os.path.getsize(final) > 2000:
            print(f"skip {role}/{idx}")
            continue

        parts = sentences(slide.get("narration", ""))
        files = []
        for i, sent in enumerate(parts):
            pitch = PITCH_PATTERN[i % len(PITCH_PATTERN)]
            part = os.path.join(work, f"s{idx:02d}_{i:02d}.mp3")
            await synth_sentence(sent, part, pitch)
            files.append(part)
            # فاصل: أطول بعد السؤال، أقصر بعد النقطة
            gap = silence_long if sent.endswith(("؟", "!")) else silence_short
            files.append(gap)

        listing = os.path.join(work, f"list_{idx:02d}.txt")
        with open(listing, "w", encoding="utf-8") as fh:
            for f in files:
                fh.write(f"file '{f.replace(chr(92), '/')}'\n")

        raw = os.path.join(work, f"raw_{idx:02d}.mp3")
        subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", raw],
                       capture_output=True)
        subprocess.run([
            FFMPEG, "-y", "-i", raw, "-af", FFMPEG_AUDIO_FILTER,
            "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "128k", final,
        ], capture_output=True)
        print(f"audio {role}/slide-{idx:02d}: {len(parts)} جملة")


def main():
    sys.path.insert(0, HERE)
    from content_roles import ROLES

    audio_root = os.path.join(HERE, "audio")
    os.makedirs(audio_root, exist_ok=True)

    async def run():
        for role, data in ROLES.items():
            print(f"== {role} ({data['label']}) ==")
            await synth_role(role, data["slides"], audio_root)

    asyncio.run(run())


if __name__ == "__main__":
    main()
