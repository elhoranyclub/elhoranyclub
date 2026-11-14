# -*- coding: utf-8 -*-
"""يجهّز لقطات الدليل التفاعلي كصور مضغوطة في static/guide/shots/."""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "shots")
DST = os.path.join(ROOT, "static", "guide", "shots")

# اللقطات المستعملة في الدليل (بالاسم في المحتوى)
PHONE_SHOTS = {
    "01-home.png", "58-home-full.png", "10-register.png", "09-pricing.png", "02-news.png",
    "03-tournaments.png", "04-tournaments-live.png", "08-contact.png", "23-member-profile.png",
    "22-member-card.png", "24-member-dependents.png", "25-renew-1.png", "26-renew-2.png",
    "05-courses.png", "27-notifications.png", "21-member-services.png", "28-member-payments.png",
}


def main():
    sys.path.insert(0, os.path.join(ROOT, "apps", "pages"))
    from guide_content import SECTIONS

    used = set()
    for section in SECTIONS:
        for block in section["blocks"]:
            if block.get("type") == "image":
                used.add(block["file"])

    os.makedirs(DST, exist_ok=True)
    total = 0
    for name in sorted(used):
        src = os.path.join(SRC, name)
        if not os.path.exists(src):
            print("missing:", name)
            continue
        im = Image.open(src).convert("RGB")
        width = 430 if name in PHONE_SHOTS else 900
        if im.width > width:
            im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
        out = os.path.join(DST, name.replace(".png", ".jpg"))
        im.save(out, "JPEG", quality=82, optimize=True, progressive=True)
        total += os.path.getsize(out)
        print(f"{name} -> {os.path.basename(out)}  {os.path.getsize(out)//1024} KB")
    print(f"total {total/1_048_576:.2f} MB in {DST}")


if __name__ == "__main__":
    main()
