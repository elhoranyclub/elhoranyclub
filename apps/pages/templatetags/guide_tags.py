# -*- coding: utf-8 -*-
"""تاغات قالب الدليل التفاعلي — ترسم البلوكات (نقاط / خطوات / كروت / جدول / صور)."""
from django import template
from django.templatetags.static import static
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def guide_block(block):
    """يرسم بلوك واحد من محتوى الدليل."""
    kind = block.get("type")

    if kind == "bullets":
        items = "".join(f"<li>{i}</li>" for i in block["items"])
        return mark_safe(f'<ul class="g-bullets">{items}</ul>')

    if kind == "steps":
        items = "".join(f"<li>{i}</li>" for i in block["items"])
        return mark_safe(f'<ol class="g-steps">{items}</ol>')

    if kind == "cards":
        cells = "".join(
            f'<div class="g-card"><h3>{title}</h3><p>{body}</p></div>'
            for title, body in block["items"]
        )
        return mark_safe(f'<div class="g-cards">{cells}</div>')

    if kind == "table":
        head = "".join(f"<th>{h}</th>" for h in block["headers"])
        rows = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in block["rows"]
        )
        return mark_safe(
            f'<div class="g-tablewrap"><table class="g-table"><thead><tr>{head}</tr></thead>'
            f"<tbody>{rows}</tbody></table></div>"
        )

    if kind == "image":
        caption = f'<figcaption>{escape(block["caption"])}</figcaption>' if block.get("caption") else ""
        width = block.get("width", 420)
        url = static(f"guide/shots/{block['file']}")
        return mark_safe(
            f'<figure class="g-shot"><img src="{url}" '
            f'alt="{escape(block.get("caption", ""))}" style="max-width:{width}px">{caption}</figure>'
        )

    if kind == "note":
        tone = block.get("tone", "warn")
        return mark_safe(f'<p class="g-note {escape(tone)}">{block["text"]}</p>')

    if kind == "title":
        return mark_safe(f'<h3 class="g-subtitle">{block["text"]}</h3>')

    return mark_safe("")
